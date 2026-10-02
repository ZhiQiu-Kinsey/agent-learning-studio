"""读码场景：从白名单源码计算符号、“本课新增”与批注定位。

符号只来自 Python ast 对真实文件的解析，不手写。比较依据是“名称 + 规范化源码哈希”：
规范化形式为 ``ast.dump(node, include_attributes=False)``，因此空白、注释和行号移动不算变化，
文档字符串和任何语法层面的改动都算变化。
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from server.content_schema import AnnotatedSource, LessonContent, WhatsNew
from server.curriculum import LessonValidationError

# 模块级常量按 Python 约定用全大写名称识别，如 TOOLS、SYSTEM_PROMPT、INPUT_MODEL。
_CONSTANT = re.compile(r"_?[A-Z][A-Z0-9_]*\Z")
# 与前端按行切分保持一致：只把 \r\n、\r、\n 当作换行（ast 的行号也只认这三种）。
_NEWLINE = re.compile(r"\r\n|\r|\n")
_cache: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
# 同一课内出现同名符号时：沿用优先于变化，变化优先于新增。
_PRIORITY = {"unchanged": 2, "changed": 1, "added": 0}


def split_lines(text: str) -> list[str]:
    lines = _NEWLINE.split(text)
    if lines and lines[-1] == "":
        lines.pop()  # 文件末尾的换行不构成新的一行
    return lines


def line_count(text: str) -> int:
    return len(split_lines(text))


def _names(node: ast.stmt) -> tuple[str, list[str]] | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "function", [node.name]
    if isinstance(node, ast.ClassDef):
        return "class", [node.name]
    if isinstance(node, ast.Assign):
        names = [target.id for target in node.targets
                 if isinstance(target, ast.Name) and _CONSTANT.fullmatch(target.id)]
        return ("constant", names) if names else None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and _CONSTANT.fullmatch(node.target.id):
        return "constant", [node.target.id]
    return None


def extract_symbols(text: str) -> list[dict[str, Any]]:
    """列出顶层函数、类与常量及其起止行号（含装饰器）；语法错误直接抛出 SyntaxError。"""
    symbols = []
    for node in ast.parse(text).body:
        found = _names(node)
        if found is None:
            continue
        kind, names = found
        start = min([node.lineno, *(item.lineno for item in getattr(node, "decorator_list", []))])
        digest = hashlib.sha256(ast.dump(node, include_attributes=False).encode("utf-8")).hexdigest()[:16]
        for name in names:
            symbols.append({"name": name, "kind": kind, "start": start, "end": node.end_lineno or node.lineno,
                            "hash": digest})
    return symbols


def classify(current: Iterable[dict[str, Any]], baseline: Iterable[dict[str, Any]] | None) -> dict[str, str]:
    """按名称比较：基准中有同名同哈希为沿用，同名不同哈希为变化，没有同名为新增。

    没有基准（第一门课）时全部记为新增。返回 {name: status}；同名多处定义时任一处相同即视为沿用。
    """
    known: dict[str, set[str]] = {}
    for symbol in baseline or []:
        known.setdefault(symbol["name"], set()).add(symbol["hash"])
    statuses: dict[str, str] = {}
    for symbol in current:
        hashes = known.get(symbol["name"])
        status = "added" if not hashes else "unchanged" if symbol["hash"] in hashes else "changed"
        previous = statuses.get(symbol["name"])
        if previous is None or _PRIORITY[status] > _PRIORITY[previous]:
            statuses[symbol["name"]] = status
    return statuses


def _code_blocks(model: LessonContent) -> list[Any]:
    return list(model.scenes.code.blocks) if model.scenes.code else []


def compare_target(model: LessonContent) -> str | None:
    """whats-new 块声明的对比课程（slug 或别名）；没有声明返回 None。"""
    return next((block.compare_with for block in _code_blocks(model)
                 if isinstance(block, WhatsNew) and block.compare_with), None)


def validate_code_scene(model: LessonContent, sources: list[dict[str, Any]], read: Callable[[str], str],
                        location: str) -> None:
    """annotated-source 的 path 必须在本课 sources 中，行号不得超出文件行数，批注须落在声明的范围内。"""
    declared = {source["path"] for source in sources}
    files: dict[str, list[str]] = {}
    for block in _code_blocks(model):
        if not isinstance(block, AnnotatedSource):
            continue
        where = f"{location}: scenes.code 块 {block.id}"
        if block.path not in declared:
            raise LessonValidationError(f"{where}: path「{block.path}」不在本课 sources 中")
        if block.path not in files:
            files[block.path] = split_lines(read(block.path))
        lines = files[block.path]
        total = len(lines)
        for name in ("start", "end"):
            value = getattr(block, name)
            if value is not None and value > total:
                raise LessonValidationError(f"{where}: {name}={value} 超出文件行数 {total}")
        low, high = block.start or 1, block.end or total
        for note in block.notes:
            if note.line > total:
                raise LessonValidationError(f"{where}: 批注 {note.id} 的行号 {note.line} 超出文件行数 {total}")
            if not low <= note.line <= high:
                raise LessonValidationError(f"{where}: 批注 {note.id} 的行号 {note.line} 不在 {low}–{high} 范围内")
            if note.anchor not in lines[note.line - 1]:
                raise LessonValidationError(
                    f"{where}: 批注 {note.id} 的锚点「{note.anchor}」不在第 {note.line} 行"
                    f"（该行是「{lines[note.line - 1].strip()[:60]}」）；源码可能已移动，请重新对准批注")
        for fold in block.folds:
            if not low <= fold.start <= fold.end <= high:
                raise LessonValidationError(f"{where}: 折叠 {fold.id} 的 {fold.start}–{fold.end} 不在 {low}–{high} 范围内")


# 批注密度门槛：展示范围内每 NOTE_EVERY 个非空、未折叠的行至少一条批注，连续无批注不超过 MAX_GAP 行。
NOTE_EVERY = 8
MAX_GAP = 12


def note_density(block: AnnotatedSource, lines: list[str]) -> dict[str, int]:
    """统计一个读码块的可见非空行数、批注数与最长无批注空段（只数非空、未折叠的行）。"""
    low, high = block.start or 1, block.end or len(lines)
    folded = {line for fold in block.folds for line in range(fold.start, fold.end + 1)}
    noted = {note.line for note in block.notes}
    visible = gap = longest = 0
    for number in range(low, high + 1):
        if number in folded or not lines[number - 1].strip():
            continue
        visible += 1
        gap = 0 if number in noted else gap + 1
        longest = max(longest, gap)
    return {"lines": visible, "notes": len(block.notes), "longest_gap": longest}


def density_issues(model: LessonContent, read: Callable[[str], str]) -> list[str]:
    """不满足批注密度门槛的读码块，返回“块 id：原因”列表（基线比对由调用方完成）。"""
    issues = []
    for block in _code_blocks(model):
        if not isinstance(block, AnnotatedSource):
            continue
        stats = note_density(block, split_lines(read(block.path)))
        needed = -(-stats["lines"] // NOTE_EVERY)
        if stats["notes"] < needed:
            issues.append(f"{block.id}：{stats['lines']} 行只有 {stats['notes']} 条批注，至少需要 {needed} 条")
        if stats["longest_gap"] > MAX_GAP:
            issues.append(f"{block.id}：连续 {stats['longest_gap']} 行没有批注，最多 {MAX_GAP} 行")
    return issues


def _file_symbols(path: Path) -> list[dict[str, Any]]:
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _cache:
        if len(_cache) > 256:
            _cache.clear()
        _cache[key] =extract_symbols(path.read_text(encoding="utf-8"))
    return [dict(symbol) for symbol in _cache[key]]


def _files(spec: dict[str, Any]) -> list[dict[str, Any]]:
    from server.catalog import _safe_file  # 延迟导入：catalog 在加载课程时也会导入本模块

    files = []
    for source in spec["sources"]:
        path = _safe_file(spec["root"], source["path"], "lesson sources", source=True)
        python = path.suffix.casefold() == ".py"
        files.append({"path": source["path"], "language": source["language"],
                      "lines": line_count(path.read_text(encoding="utf-8")),
                      "symbols": _file_symbols(path) if python else []})
    return files


def _baseline(spec: dict[str, Any], lessons: list[dict[str, Any]]) -> dict[str, Any] | None:
    """whats-new 声明的对比课；未声明或对比课不可用时取目录顺序中的上一门可用课。"""
    explicit = spec.get("code_compare")
    if explicit:
        match = next((item for item in lessons if explicit == item["id"] or explicit in item["aliases"]), None)
        if match is not None:
            return match
    ids = [item["id"] for item in lessons]
    if spec["id"] not in ids:
        return None
    index = ids.index(spec["id"])
    return lessons[index - 1] if index > 0 else None


def _ref(path: str, symbol: dict[str, Any]) -> dict[str, Any]:
    return {"name": symbol["name"], "kind": symbol["kind"], "path": path,
            "start": symbol["start"], "end": symbol["end"]}


def lesson_code(spec: dict[str, Any], lessons: list[dict[str, Any]], learning: dict[str, Any]) -> dict[str, Any]:
    """GET /api/lessons/{id}/code 的响应体；learning 是已合并译文层的 content v2 输出。"""
    files = _files(spec)
    baseline_spec = _baseline(spec, lessons)
    baseline = ([symbol for item in _files(baseline_spec) for symbol in item["symbols"]]
                if baseline_spec else None)
    statuses = classify([symbol for item in files for symbol in item["symbols"]], baseline)
    groups: dict[str, list[dict[str, Any]]] = {"added": [], "changed": [], "unchanged": []}
    for item in files:
        for symbol in item["symbols"]:
            symbol["status"] = statuses[symbol["name"]]
            groups[symbol["status"]].append(_ref(item["path"], symbol))
    blocks = (learning.get("scenes", {}).get("code") or {}).get("blocks", [])
    annotations = [{key: block[key] for key in ("id", "path", "start", "end", "notes", "folds")}
                   for block in blocks if block.get("type") == "annotated-source"]
    compare = ({"id": baseline_spec["id"], "number": baseline_spec["number"], "title": baseline_spec["title"]}
               if baseline_spec else None)
    return {"lesson_id": spec["id"], "files": files,
            "whats_new": {"compare_with": compare, **groups},
            "annotations": annotations}
