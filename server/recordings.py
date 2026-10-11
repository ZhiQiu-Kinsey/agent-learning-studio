"""随课分发的真实运行录制（recorded_run）：格式、哈希、导出与校验。

录制只能由导出脚本从运行存储原样导出，事件只把 provenance 由 real_run 改为 recorded_run。
校验规则与 docs/architecture/event-envelope-v2.md 第 6 节一致；事件结构通过
server/envelope.py 的 EnvelopeBuilder 逐条重放比对，信封与 span 规则不另写一份。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

from course.i18n import RUNTIME_LOCALES
from server.envelope import SPAN_EVENTS, EnvelopeBuilder
from server.providers import PROVIDERS

# 2：元数据加入运行语言 locale（与 run_start 事件一致）。
RECORDING_SCHEMA_VERSION = 2
RECORDINGS_DIR = "recordings"
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME_MAX_LENGTH = 64
RUN_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
METADATA_FIELDS = ("schema_version", "lesson", "exercise_id", "run_id", "status", "model", "provider_id",
                   "provider_label", "representation", "sdk", "recorded_at", "platform_version",
                   "source_hash", "integrity_hash", "event_count", "locale")
# 运行存储中的状态；“失败”的运行在存储里记为 error。
RECORDABLE_STATUSES = ("completed", "error")
RECORDED_REPRESENTATIONS = ("http_body", "sdk_standardized")
TEST_ADAPTER_NAME = "deterministic-test-adapter"
# 平台内部的非模型服务商：确定性测试与本地 Python 课程，不能作为真实模型录制。
NON_MODEL_PROVIDERS = ("testing", "local")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 小写、去掉 - _ 空格后比较的认证字段名。
AUTH_FIELDS = {"authorization", "proxyauthorization", "apikey", "xapikey", "apisecret", "secretkey",
               "accesstoken", "clientsecret"}
KEY_PATTERNS = (
    (re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9][A-Za-z0-9_\-]{15,}"), "sk- 前缀密钥"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "Google API Key"),
    (re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{30,}"), "GitHub 令牌"),
    (re.compile(r"(?<![A-Za-z0-9])xox[abposr]-[A-Za-z0-9\-]{10,}"), "Slack 令牌"),
    (re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"), "AWS 访问密钥"),
    (re.compile(r"(?i)\bbearer\s+(?!\[REDACTED\])[A-Za-z0-9._~+/\-]{12,}=*"), "Bearer 认证头"),
)
PATH_PATTERNS = (
    re.compile(r"(?i)\b[a-z]:[\\/]+(?:users|documents and settings)[\\/]+[^\\/\s\"']+"),
    re.compile(r"(?i)(?<![\w.\-])/(?:users|home)/[^/\s\"']+"),
)
# 配置的密钥短于此长度时不做子串比对，避免误报；真实服务商密钥都远长于此。
MIN_KEY_LENGTH = 8


class RecordingError(Exception):
    """录制不可用；location 只描述位置，不包含敏感值。"""

    code = "recording_invalid"

    def __init__(self, message: str, location: str | None = None):
        super().__init__(f"{location}：{message}" if location else message)
        self.message, self.location = message, location


class RecordingInvalid(RecordingError):
    code = "recording_invalid"


class RecordingStale(RecordingError):
    code = "recording_stale"


class ExportRefused(Exception):
    """导出前检查未通过；消息不回显敏感值。"""


# ---------- 哈希 ----------

def canonical_json(value) -> bytes:
    """规范化 JSON：键排序、无空白、保留非 ASCII 字符、UTF-8 编码；拒绝 NaN/Infinity。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def integrity_hash(events: list) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(events)).hexdigest()


def source_files(spec: dict) -> list[str]:
    """参与源码哈希的文件（相对项目根的 POSIX 路径）：先 lesson.json，再按路径排序的 sources。"""
    manifest = f"lessons/{spec['module']}/lesson.json"
    sources = sorted({source["path"] for source in spec["sources"]} - {manifest})
    return [manifest, *sources]


def source_hash(spec: dict) -> str:
    """逐个文件计算 sha256（先把 CRLF 统一为 LF），按 `<hex>  <path>\\n` 拼接后再求 sha256。"""
    root = Path(spec["root"])
    outer = hashlib.sha256()
    for relative in source_files(spec):
        content = root.joinpath(*relative.split("/")).read_bytes().replace(b"\r\n", b"\n")
        outer.update(f"{hashlib.sha256(content).hexdigest()}  {relative}\n".encode("utf-8"))
    return "sha256:" + outer.hexdigest()


def platform_version(root: Path) -> str:
    """pyproject 版本 + git 提交：`0.1.0+g<12 位提交>`，已跟踪文件有未提交改动时追加 `.dirty`。"""
    root = Path(root)
    try:
        version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, ValueError):
        version = "unknown"
    try:
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                                text=True, timeout=10, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return version
    if not COMMIT_PATTERN.fullmatch(commit):
        return version
    return f"{version}+g{commit[:12]}" + (".dirty" if dirty else "")


# ---------- 敏感内容检查 ----------

def default_private_paths() -> list[str]:
    """本机私有路径：用户主目录与项目所在目录（两种分隔符）。只收录足够具体的路径。"""
    values = []
    for path in (Path.home(), PROJECT_ROOT):
        if len(Path(path).parts) >= 3:
            values.extend({str(path), Path(path).as_posix()})
    return values


def _clean_key(text: str) -> str:
    return re.sub(r"[-_\s]", "", text).lower()


def find_sensitive(value, keys=(), private_paths=None) -> list[tuple[str, str]]:
    """返回 [(位置, 问题)]；位置用 JSON 路径表示，不包含任何被检出的值。"""
    keys = [key for key in keys if isinstance(key, str) and len(key) >= MIN_KEY_LENGTH]
    paths = [path.casefold() for path in (default_private_paths() if private_paths is None else private_paths)
             if path]
    findings: list[tuple[str, str]] = []

    def problems(text: str) -> list[str]:
        found = []
        if any(key in text for key in keys):
            found.append("含与当前已配置密钥相同的字符串")
        found.extend("疑似" + label for pattern, label in KEY_PATTERNS if pattern.search(text))
        folded = text.casefold()
        if any(pattern.search(text) for pattern in PATH_PATTERNS) or any(path in folded for path in paths):
            found.append("含本机私有路径")
        return found

    def visit(node, location):
        if isinstance(node, dict):
            for key, child in node.items():
                key = str(key)
                key_problems = problems(key)
                name = "<字段名>" if key_problems else key
                path = f"{location}.{name}" if location else name
                findings.extend((path, "字段名" + problem) for problem in key_problems)
                if _clean_key(key) in AUTH_FIELDS and child not in (None, "", [], {}):
                    findings.append((path, "认证字段（authorization / api_key 等）"))
                visit(child, path)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{location}[{index}]")
        elif isinstance(node, str):
            findings.extend((location, problem) for problem in problems(node))

    visit(value, "")
    return findings


# ---------- 文档校验 ----------

def _fail(message, location=None):
    raise RecordingInvalid(message, location)


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_metadata_shape(metadata):
    if not isinstance(metadata, dict) or set(metadata) != set(METADATA_FIELDS):
        _fail("元数据字段必须恰好为：" + "、".join(METADATA_FIELDS), "metadata")
    if type(metadata["schema_version"]) is not int or metadata["schema_version"] != RECORDING_SCHEMA_VERSION:
        _fail(f"录制格式版本必须为 {RECORDING_SCHEMA_VERSION}", "metadata.schema_version")
    for field in ("lesson", "exercise_id", "model", "provider_id", "provider_label", "recorded_at",
                  "platform_version", "source_hash", "integrity_hash"):
        if not _is_text(metadata[field]):
            _fail("必须是非空字符串", f"metadata.{field}")
    if not RUN_ID_PATTERN.fullmatch(str(metadata["run_id"])):
        _fail("必须是 32 位十六进制运行编号", "metadata.run_id")
    if metadata["status"] not in RECORDABLE_STATUSES:
        _fail("只接受 completed 或 error", "metadata.status")
    if type(metadata["event_count"]) is not int or metadata["event_count"] < 2:
        _fail("必须是不小于 2 的整数", "metadata.event_count")
    if metadata["locale"] not in RUNTIME_LOCALES:
        _fail("必须是平台支持的运行语言：" + "、".join(RUNTIME_LOCALES), "metadata.locale")
    try:
        datetime.fromisoformat(metadata["recorded_at"])
    except ValueError:
        _fail("必须是 ISO 8601 时间", "metadata.recorded_at")
    for field in ("source_hash", "integrity_hash"):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", metadata[field]):
            _fail("必须形如 sha256:<64 位十六进制>", f"metadata.{field}")


def _check_representation(metadata):
    """表示层级必须与服务商一致：百炼原生 HTTP 是 http_body，其余服务商经 SDK，是 sdk_standardized。"""
    representation, sdk, provider = metadata["representation"], metadata["sdk"], metadata["provider_id"]
    if representation not in RECORDED_REPRESENTATIONS:
        _fail("必须是 http_body 或 sdk_standardized", "metadata.representation")
    if provider in NON_MODEL_PROVIDERS or provider not in PROVIDERS:
        _fail("不是真实模型服务商", "metadata.provider_id")
    if representation == "http_body":
        if sdk is not None:
            _fail("http_body 不能附带 SDK 信息；SDK 数据不能标成原始 HTTP 请求体", "metadata.sdk")
        if provider != "bailian":
            _fail("只有百炼原生 HTTP 路径产生 http_body；该服务商经 SDK 调用，必须标为 sdk_standardized",
                  "metadata.representation")
        return
    if provider == "bailian":
        _fail("百炼原生 HTTP 路径不经过 SDK，不能标为 sdk_standardized", "metadata.representation")
    if not isinstance(sdk, dict) or set(sdk) != {"name", "version"}:
        _fail("sdk_standardized 必须附 SDK 名称和版本 {name, version}", "metadata.sdk")
    if not _is_text(sdk["name"]) or not _is_text(sdk["version"]):
        _fail("SDK 名称和版本必须是非空字符串", "metadata.sdk")
    if sdk["name"] == TEST_ADAPTER_NAME:
        _fail("确定性测试适配器不是真实模型", "metadata.sdk")


def check_events(events, metadata):
    """用 EnvelopeBuilder 逐条重放：seq、span、actor、表示层级与来源都必须与平台生成的一致。"""
    if not isinstance(events, list) or len(events) < 2:
        _fail("必须是至少包含 run_start 与 done 的数组", "events")
    if not all(isinstance(event, dict) for event in events):
        _fail("每个事件都必须是对象", "events")
    run_id = metadata["run_id"]
    builder = EnvelopeBuilder(run_id, provenance="recorded_run", representation=metadata["representation"],
                              sdk=metadata["sdk"])
    for index, event in enumerate(events):
        location = f"events[{index}]"
        if event.get("provenance") != "recorded_run":
            _fail("provenance 必须为 recorded_run", location + ".provenance")
        kind, data, number, timestamp = (event.get(key) for key in ("type", "data", "round", "timestamp"))
        if not _is_text(kind) or not isinstance(data, dict) or not _is_text(timestamp) \
                or not (number is None or type(number) is int):
            _fail("type、data、round 或 timestamp 的类型不符合信封 v2", location)
        expected = builder.build(kind, data, number, timestamp)
        if event != expected:
            fields = sorted(set(event) ^ set(expected)) or [key for key in expected if event[key] != expected[key]]
            _fail("不符合信封 v2 规则（seq 连续、span 配对、表示层级）：" + "、".join(fields), location)
        if kind in SPAN_EVENTS and SPAN_EVENTS[kind].get("model_payload") and "representation" in data \
                and data["representation"] != metadata["representation"]:
            _fail("data.representation 与录制的表示层级不一致", location + ".data.representation")
    kinds = [event["type"] for event in events]
    if kinds[0] != "run_start" or kinds.count("run_start") != 1:
        _fail("第一个事件必须是唯一的 run_start", "events[0]")
    if kinds[-1] != "done" or kinds.count("done") != 1:
        _fail("最后一个事件必须是唯一的 done", f"events[{len(events) - 1}]")
    if events[-1]["data"].get("status") != metadata["status"]:
        _fail("done 的状态与元数据不一致", f"events[{len(events) - 1}].data.status")
    if "request" not in kinds:
        _fail("没有模型请求，无法证明来自真实模型", "events")
    start = events[0]["data"]
    expected_start = {"mode": "live", "lesson_id": metadata["lesson"], "model": metadata["model"],
                      "provider_id": metadata["provider_id"], "provider_label": metadata["provider_label"],
                      "trace_representation": metadata["representation"], "locale": metadata["locale"]}
    for key, value in expected_start.items():
        if start.get(key) != value:
            _fail("与录制元数据不一致", f"events[0].data.{key}")


def validate_document(document, spec: dict, keys=(), private_paths=None) -> dict:
    """校验一份录制；通过时返回元数据。结构、完整性或安全问题抛 RecordingInvalid，源码变化抛 RecordingStale。"""
    if not isinstance(document, dict) or set(document) != {"metadata", "events"}:
        _fail("录制文件必须恰好包含 metadata 与 events")
    findings = find_sensitive(document, keys, private_paths)
    if findings:
        location, problem = findings[0]
        raise RecordingInvalid(f"{problem}（共 {len(findings)} 处疑似密钥或本机私有路径）", location)
    metadata, events = document["metadata"], document["events"]
    _check_metadata_shape(metadata)
    if metadata["lesson"] != spec["id"]:
        _fail("录制的课程与所在课程目录不一致", "metadata.lesson")
    if not isinstance(events, list) or metadata["event_count"] != len(events):
        _fail("事件数量与 event_count 不一致", "metadata.event_count")
    try:
        actual = integrity_hash(events)
    except ValueError:
        _fail("事件包含无法规范化的数值", "events")
    if actual != metadata["integrity_hash"]:
        _fail("完整性哈希不一致，事件内容被修改过", "metadata.integrity_hash")
    _check_representation(metadata)
    check_events(events, metadata)
    try:
        current = source_hash(spec)
    except OSError:
        current = None
    if current != metadata["source_hash"]:
        raise RecordingStale("源码已变化，请重新录制", "metadata.source_hash")
    if not any(exercise["id"] == metadata["exercise_id"] for exercise in spec["exercises"]):
        _fail("练习不存在于当前课程", "metadata.exercise_id")
    if metadata["locale"] not in spec["runtime"]["locales"]:
        _fail("本课不支持这种运行语言", "metadata.locale")
    return metadata


def _reject_constant(value):
    raise ValueError("不支持 NaN 或 Infinity")


def load_document(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except (OSError, ValueError):
        raise RecordingInvalid("无法读取有效 JSON") from None


# ---------- 按课程读取 ----------

def recordings_dir(spec: dict) -> Path:
    return Path(spec["root"]) / "lessons" / spec["module"] / RECORDINGS_DIR


def valid_name(name) -> bool:
    return isinstance(name, str) and len(name) <= NAME_MAX_LENGTH and bool(NAME_PATTERN.fullmatch(name))


def recording_path(spec: dict, name: str) -> Path | None:
    """名称合法且文件位于本课 recordings/ 内（含符号链接解析）时返回路径。"""
    if not valid_name(name):
        return None
    directory = recordings_dir(spec)
    path = directory / f"{name}.json"
    if not path.is_file() or not path.resolve().is_relative_to(directory.resolve()):
        return None
    return path


def recording_names(spec: dict) -> list[str]:
    directory = recordings_dir(spec)
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json") if recording_path(spec, path.stem))


def read_recording(spec: dict, name: str, keys=(), private_paths=None) -> tuple[dict, list]:
    """读取并完整校验；路径不存在时抛 FileNotFoundError。"""
    path = recording_path(spec, name)
    if path is None:
        raise FileNotFoundError(name)
    document = load_document(path)
    metadata = validate_document(document, spec, keys, private_paths)
    return metadata, document["events"]


def list_recordings(spec: dict, keys=(), private_paths=None) -> list[dict]:
    """列出本课录制；源码过期的录制仍返回元数据，结构或安全检查失败的不返回任何内容。"""
    items = []
    for name in recording_names(spec):
        try:
            metadata, _ = read_recording(spec, name, keys, private_paths)
            items.append({"name": name, "valid": True, "error_code": None, "metadata": metadata})
        except RecordingStale:
            document = load_document(recording_path(spec, name))
            items.append({"name": name, "valid": False, "error_code": RecordingStale.code,
                          "metadata": document["metadata"]})
        except (RecordingInvalid, FileNotFoundError):
            items.append({"name": name, "valid": False, "error_code": RecordingInvalid.code, "metadata": None})
    return items


def validate_lesson_recordings(root: Path, specs: list[dict], keys=(), private_paths=None):
    """校验 lessons/*/recordings/ 下的全部文件；返回 (通过数, [(相对路径, 错误)])。"""
    root = Path(root).resolve()
    by_module = {spec["module"]: spec for spec in specs}
    passed, failures = 0, []
    for directory in sorted((root / "lessons").glob(f"*/{RECORDINGS_DIR}")):
        spec = by_module.get(directory.parent.name)
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if spec is None:
                failures.append((relative, "所在目录没有课程实现声明 lesson.json"))
            elif path.suffix != ".json" or not path.is_file() or recording_path(spec, path.stem) is None:
                failures.append((relative, "录制文件名必须是 kebab-case 的 <name>.json"))
            else:
                try:
                    validate_document(load_document(path), spec, keys, private_paths)
                    passed += 1
                except RecordingError as error:
                    failures.append((relative, str(error)))
    return passed, failures


# ---------- 导出 ----------

def read_stored_run(db_path: Path, run_id: str) -> tuple[dict, list[dict]]:
    """只读打开运行存储；不经过 RunStore，避免把正在进行的运行标成 interrupted。"""
    db_path = Path(db_path)
    if not RUN_ID_PATTERN.fullmatch(run_id or ""):
        raise ExportRefused("运行编号必须是 32 位十六进制。")
    if not db_path.is_file():
        raise ExportRefused("找不到运行存储，请先在平台中完成一次真实运行。")
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise ExportRefused("运行记录不存在或已被清除。")
        texts = [text for (text,) in connection.execute(
            "SELECT event FROM events WHERE run_id = ? ORDER BY seq", (run_id,))]
    finally:
        connection.close()
    return dict(row), [json.loads(text) for text in texts]


def _check_exportable(run: dict, events: list[dict]):
    if run["mode"] != "live":
        raise ExportRefused("只能导出真实模型（live）运行；离线确定性测试运行不能作为录制。")
    if run["status"] not in RECORDABLE_STATUSES:
        raise ExportRefused(f"运行状态为 {run['status']}；只能导出已完成（completed）或失败（error）的运行，"
                            "已取消、中断或仍在进行的运行不能导出。")
    if run["provenance"] != "real_run" or any(event.get("provenance") != "real_run" for event in events):
        raise ExportRefused("运行事件的来源必须全部是 real_run。")
    if run["representation"] not in RECORDED_REPRESENTATIONS:
        raise ExportRefused("该运行没有模型请求与响应，不能证明来自真实模型。")
    if not events or events[-1].get("type") != "done":
        raise ExportRefused("运行事件不完整（缺少 done）。")


def _source_modified_after(spec: dict, created_at: str) -> bool:
    started = datetime.fromisoformat(created_at).timestamp()
    root = Path(spec["root"])
    return any(os.stat(root.joinpath(*relative.split("/"))).st_mtime > started for relative in source_files(spec))


def build_recording(run: dict, events: list[dict], spec: dict, root: Path) -> dict:
    """组装录制文档：事件只改 provenance，其余字段原样保留。"""
    recorded = []
    for event in events:
        copy = dict(event)  # 只替换顶层 provenance；data 等字段与存储中的对象完全相同。
        copy["provenance"] = "recorded_run"
        recorded.append(copy)
    sdk = next((event["sdk"] for event in events
                if SPAN_EVENTS.get(event.get("type"), {}).get("model_payload")), None)
    metadata = {
        "schema_version": RECORDING_SCHEMA_VERSION,
        "lesson": run["lesson_id"],
        "exercise_id": run["exercise_id"],
        "run_id": run["run_id"],
        "status": run["status"],
        "model": run["model"],
        "provider_id": run["provider_id"],
        "provider_label": events[0].get("data", {}).get("provider_label"),
        "representation": run["representation"],
        "sdk": sdk,
        "recorded_at": run["created_at"],
        "platform_version": platform_version(root),
        "source_hash": source_hash(spec),
        "integrity_hash": integrity_hash(recorded),
        "event_count": len(recorded),
        "locale": run.get("locale") or "zh-CN",
    }
    return {"metadata": metadata, "events": recorded}


def export_run(db_path: Path, run_id: str, name: str, *, root: Path, specs: list[dict], keys=(),
               private_paths=None, replace: bool = False) -> Path:
    """从运行存储导出一份录制并写入 lessons/<课程目录>/recordings/<name>.json。"""
    if not valid_name(name):
        raise ExportRefused(f"录制名称必须是 kebab-case（小写字母、数字、连字符），不超过 {NAME_MAX_LENGTH} 个字符。")
    run, events = read_stored_run(db_path, run_id)
    _check_exportable(run, events)
    spec = next((item for item in specs if item["id"] == run["lesson_id"]), None)
    if spec is None:
        raise ExportRefused("该运行所属课程在当前项目中不存在。")
    if _source_modified_after(spec, run["created_at"]):
        raise ExportRefused("课程源码在这次运行之后被修改过，录制无法对应当前源码；请重新运行后再导出。")
    document = build_recording(run, events, spec, root)
    findings = find_sensitive(document, keys, private_paths)
    if findings:
        raise ExportRefused("发现疑似密钥或本机私有路径，已拒绝导出（不显示具体内容）：\n  "
                            + "\n  ".join(f"{location}：{problem}" for location, problem in findings))
    try:
        validate_document(document, spec, keys, private_paths)
    except RecordingError as error:
        raise ExportRefused(f"导出结果未通过录制校验：{error}") from None
    directory = recordings_dir(spec)
    target = directory / f"{name}.json"
    if target.exists() and not replace:
        raise ExportRefused("同名录制已存在；确认替换请加 --replace。")
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".{name}.json.tmp"
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, target)
    return target
