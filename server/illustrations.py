"""教学示意（provenance=illustration）的契约。

示意是作者写的合成事件序列，与真实运行共用同一个舞台渲染器，因此必须满足真实运行的
结构约束，又不能让人误以为是运行记录：
- 事件类型与 span 规则沿用 server/envelope.py 的 SPAN_EVENTS；开始与结束成对、顺序合法；
- 工具调用 id 必须是示例 id（含 example），结果通过 tool_call_id 对应已发出的调用；
- 轮次不递减；answer/error 之后不再有模型或工具事件；
- 不出现执行测量值：耗时、token 用量、费用、"12 passed in 0.42s" 之类的输出。需要真实数值时用 recorded_run。
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from server.envelope import INSTANT_PREFIXES, SPAN_EVENTS

EXAMPLE_ID = re.compile(r"^[a-z]+_example(?:_[a-z0-9]+)*$")
MEASURED_KEYS = {"duration_ms", "elapsed", "elapsed_ms", "latency_ms", "usage", "cost", "ttft_ms",
                 "prompt_tokens", "completion_tokens", "total_tokens"}
MEASURED_TEXT = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ms|毫秒|秒)(?![a-z])|\b\d+(?:\.\d+)?s\b|\b\d+\s+(?:passed|failed)\b|\$\s?\d",
    re.IGNORECASE)


class IllustrationError(ValueError):
    pass


def _strings(value: Any, path: str = "data") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in MEASURED_KEYS:
                raise IllustrationError(f"{path}.{key}: 示意不得包含执行测量值（耗时、用量、费用）")
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def validate_illustration(events: list[dict[str, Any]], name: str = "illustration") -> None:
    open_llm = False
    open_calls: set[str] = set()
    finished = False
    last_round = 0
    for index, event in enumerate(events):
        where = f"{name}[{index}] {event.get('type')}"
        kind = event.get("type")
        if not isinstance(kind, str) or (kind not in SPAN_EVENTS and not kind.startswith(INSTANT_PREFIXES)):
            raise IllustrationError(f"{where}: 未知事件类型")
        if kind in ("run_start", "done"):
            raise IllustrationError(f"{where}: 示意只描述过程，不包含 run_start/done")
        data = event.get("data") or {}
        for path, text in _strings(data):
            if MEASURED_TEXT.search(text):
                raise IllustrationError(f"{where} {path}: 示意不得包含执行测量值，需要时请使用 recorded_run")
        round_number = event.get("round")
        if round_number is not None:
            if round_number < last_round:
                raise IllustrationError(f"{where}: 轮次不能倒退")
            last_round = round_number
        if finished and kind in ("request", "response", "tool_call", "tool_result"):
            raise IllustrationError(f"{where}: answer/error 之后不能再有模型或工具事件")
        if kind == "request":
            if open_llm:
                raise IllustrationError(f"{where}: 上一个 request 还没有 response")
            open_llm = True
        elif kind == "response":
            if not open_llm:
                raise IllustrationError(f"{where}: response 前没有 request")
            open_llm = False
        elif kind == "tool_call":
            call_id = data.get("id")
            if not isinstance(call_id, str) or not EXAMPLE_ID.fullmatch(call_id):
                raise IllustrationError(f"{where}: 调用 id 必须是示例 id（如 call_example），避免被当成真实记录")
            if call_id in open_calls:
                raise IllustrationError(f"{where}: 调用 id {call_id} 重复")
            if open_llm:
                raise IllustrationError(f"{where}: 工具调用必须在模型 response 之后")
            open_calls.add(call_id)
        elif kind == "tool_result":
            call_id = data.get("tool_call_id")
            if call_id not in open_calls:
                raise IllustrationError(f"{where}: tool_call_id 没有对应的 tool_call")
            open_calls.remove(call_id)
        elif kind in ("answer", "error"):
            finished = True
    if open_llm:
        raise IllustrationError(f"{name}: 最后一个 request 没有 response")
    if open_calls:
        raise IllustrationError(f"{name}: 工具调用没有结果：{', '.join(sorted(open_calls))}")
