"""事件信封 v2：为每条运行事件补充运行编号、序号、span 层级、来源与表示层级。

课程代码只发出 `type/round/data`；信封字段全部由平台在服务端按本文件的常量表
确定，课程无法自行声明来源或表示层级。前端镜像由 `scripts/export_trace_contract.py`
从 `trace_contract()` 生成，测试保证两边一致。
"""
from __future__ import annotations

from importlib import metadata

SCHEMA_VERSION = 2

# 数据来源：本机真实运行 / 随课分发的真实录制 / 依据已记录数据离线重算 / 教学示意。
PROVENANCES = ("real_run", "recorded_run", "offline_recompute", "illustration")
# 表示层级：传输边界原始字节 / 我们对原始字节的解析 / SDK 标准化对象 / 原生 HTTP 请求体。
REPRESENTATIONS = ("wire", "parsed", "sdk_standardized", "http_body")
# agent 层预留给多 Agent 课程；当前单 Agent 运行中 step 直接挂在 run 下。
SPAN_KINDS = ("run", "agent", "step", "llm", "tool")
DEFAULT_ACTOR = "agent"

# 区间事件与瞬时事件的唯一声明。phase：start 打开 span、end 关闭 span、instant 挂在当前 span。
# model_payload 表示事件承载模型请求或响应，只有这类事件才标注 representation。
SPAN_EVENTS = {
    "run_start": {"phase": "start", "span_kind": "run", "closed_by": "done"},
    "done": {"phase": "end", "span_kind": "run", "opened_by": "run_start"},
    "request": {"phase": "start", "span_kind": "llm", "closed_by": "response", "model_payload": True},
    "response": {"phase": "end", "span_kind": "llm", "opened_by": "request", "model_payload": True},
    "tool_call": {"phase": "start", "span_kind": "tool", "closed_by": "tool_result",
                  "pair_field": "id"},
    "tool_result": {"phase": "end", "span_kind": "tool", "opened_by": "tool_call",
                    "pair_field": "tool_call_id"},
    "answer": {"phase": "instant"},
    "error": {"phase": "instant"},
}
# 未在上表列出的课程事件（lesson.*）一律视为瞬时事件。
INSTANT_PREFIXES = ("lesson.",)
# step span 没有独立事件：同一 round 的事件属于同一个 step，round 变化即开始新 step。
STEP_SPAN = {"span_kind": "step", "derived_from": "round", "parent": "run"}

_INSTANT = {"phase": "instant"}


def span_rule(kind: str) -> dict:
    return SPAN_EVENTS.get(kind, _INSTANT)


def trace_contract() -> dict:
    """前端镜像的数据源；只包含常量，不含任何运行数据。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "provenances": list(PROVENANCES),
        "representations": list(REPRESENTATIONS),
        "span_kinds": list(SPAN_KINDS),
        "default_actor": DEFAULT_ACTOR,
        "span_events": SPAN_EVENTS,
        "instant_prefixes": list(INSTANT_PREFIXES),
        "step_span": STEP_SPAN,
    }


def sdk_identity(name: str, distribution: str | None = None) -> dict:
    """读取已安装 SDK 的版本，但不导入它；找不到时如实写 unknown。"""
    try:
        version = metadata.version(distribution or name)
    except metadata.PackageNotFoundError:
        version = "unknown"
    return {"name": name, "version": version}


class SpanTracker:
    """按 SPAN_EVENTS 把扁平事件放进 run → step → llm/tool 的树。

    规则（与 docs/architecture/event-envelope-v2.md 一致）：
    - run_start 打开根 span，done 关闭它；
    - 带 round 的事件属于该轮的 step span，round 变化时开始新 step，上一 step 中未关闭的
      llm/tool span 保持未关闭（表示没有结果，例如被停止）；
    - request/tool_call 打开 llm/tool span，父级是当前 step（无 round 时是 run）；
    - response 关闭最近一个未关闭的 llm span；tool_result 按 tool_call_id 关闭对应 tool span；
    - 找不到可关闭的 span 时按瞬时事件处理，不凭空制造配对；
    - 瞬时事件挂在最内层未关闭的 llm/tool span 下；没有时挂在当前 step（无 round 时挂在 run）。
    """

    def __init__(self):
        self._counters: dict[str, int] = {}
        self._parents: dict[str, str | None] = {}
        self._run: str | None = None
        self._step: tuple[int, str] | None = None
        self._open: list[dict] = []

    def _new(self, kind: str, parent: str | None) -> str:
        self._counters[kind] = self._counters.get(kind, 0) + 1
        span_id = f"{kind}-{self._counters[kind]}"
        self._parents[span_id] = parent
        return span_id

    def _placed(self, span_id: str, kind: str) -> tuple[str, str | None, str]:
        return span_id, self._parents[span_id], kind

    def _run_span(self) -> str:
        if self._run is None:
            self._run = self._new("run", None)
        return self._run

    def place(self, kind: str, data: dict, round_number: int | None) -> tuple[str, str | None, str]:
        rule = span_rule(kind)
        if kind == "run_start":
            return self._placed(self._run_span(), "run")
        run = self._run_span()
        if kind == "done":
            self._open.clear()
            self._step = None
            return self._placed(run, "run")
        if round_number is not None and (self._step is None or self._step[0] != round_number):
            self._open.clear()
            self._step = (round_number, self._new("step", run))
        base = self._step[1] if round_number is not None and self._step else run
        base_kind = "step" if base != run else "run"
        if rule["phase"] == "start":
            span_kind = rule["span_kind"]
            span_id = self._new(span_kind, base)
            key = data.get(rule["pair_field"]) if "pair_field" in rule else None
            self._open.append({"id": span_id, "kind": span_kind, "key": key})
            return self._placed(span_id, span_kind)
        if rule["phase"] == "end":
            match = self._match_open(rule, data)
            if match is not None:
                self._open.remove(match)
                return self._placed(match["id"], match["kind"])
        if self._open:
            current = self._open[-1]
            return self._placed(current["id"], current["kind"])
        return self._placed(base, base_kind)

    def _match_open(self, rule: dict, data: dict) -> dict | None:
        candidates = [span for span in self._open if span["kind"] == rule["span_kind"]]
        if "pair_field" in rule:
            key = data.get(rule["pair_field"])
            keyed = [span for span in candidates if span["key"] == key]
            candidates = keyed if keyed else [span for span in candidates if span["key"] is None]
        return candidates[-1] if candidates else None


class EnvelopeBuilder:
    """单次运行的信封构造器；seq 从 1 开始单调递增。调用方负责串行调用。"""

    def __init__(self, run_id: str, *, provenance: str = "real_run",
                 representation: str | None = None, sdk: dict | None = None,
                 actor: str = DEFAULT_ACTOR):
        if provenance not in PROVENANCES:
            raise ValueError("未知的 provenance。")
        if representation is not None and representation not in REPRESENTATIONS:
            raise ValueError("未知的 representation。")
        if representation == "sdk_standardized" and not sdk:
            raise ValueError("SDK 标准化数据必须注明 SDK 名称与版本。")
        if representation != "sdk_standardized" and sdk:
            raise ValueError("只有 SDK 标准化数据附带 SDK 信息。")
        self.run_id = run_id
        self.provenance = provenance
        self.representation = representation
        self.sdk = dict(sdk) if sdk else None
        self.actor = actor
        self.seq = 0
        self.spans = SpanTracker()

    def build(self, kind: str, data: dict, round_number: int | None, timestamp: str) -> dict:
        self.seq += 1
        span_id, parent_span_id, span_kind = self.spans.place(kind, data, round_number)
        model_payload = bool(span_rule(kind).get("model_payload")) and self.representation is not None
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "seq": self.seq,
            "type": kind,
            "round": round_number,
            "timestamp": timestamp,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "span_kind": span_kind,
            "actor": self.actor,
            "role": None,
            "provenance": self.provenance,
            "representation": self.representation if model_payload else None,
            "sdk": self.sdk if model_payload else None,
            "data": data,
        }
