"""声明式事件选择器的 Python 实现，语义与 frontend/src/content/selector.ts 一致。

观察点、导览与轨迹找错共用同一套选择器（server/content_schema.py 的 Selector）。这里只读事件，
用于在测试与校验中确认选择器能在真实运行事件上命中。两边的语义由共享测试向量
tests/fixtures/selector_vectors.json 约束：Python 测试与 vitest 读取同一份文件，结果必须一致。

与 TS 对应的关键约定：
- 路径如 ``data.body.choices[0].message.tool_calls[1].function.name``，按正则
  ``[^.[\\]]+|\\[\\d+\\]`` 切分；对象段只读自有键，数组段只读数组；任何一步不存在即“未找到”。
- 路径末端的值为 null（Python 的 None）、false、0 或空串时仍算找到；只有“不存在”才不匹配。
- 工具名先取 ``data.function.name``（必须是字符串），否则取 ``data.name``（必须是字符串）。
- 各条件之间是“与”关系；未给出的条件（None）不参与比较。
- ``nth`` 不是逐条事件的条件：它在全部命中里按运行顺序取第几个（从 1 数）。所以单条事件的
  ``selector_matches`` 不看它，``select_events`` / ``find_evidence`` 才看。
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

_PATH_PART = re.compile(r"[^.\[\]]+|\[\d+\]")


class _Missing:
    """路径不存在的哨兵值，对应 TS 的 undefined；与 None（JSON null）区分。"""

    _instance: "_Missing | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING: Any = _Missing()
# 逐条事件比较的条件；nth 在命中序列上取第几个，另算。
CONDITION_FIELDS = ("event", "round", "path", "span_kind", "name")
SELECTOR_FIELDS = (*CONDITION_FIELDS, "nth")


def resolve_path(value: Any, path: str) -> Any:
    """按 JSON 路径取值；不存在时返回 MISSING（不是 None）。"""
    parts = _PATH_PART.findall(path)
    if not parts:
        return MISSING
    current = value
    for part in parts:
        if current is None or current is MISSING:
            return MISSING
        if part.startswith("["):
            if not isinstance(current, list):
                return MISSING
            index = int(part[1:-1])
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            if not isinstance(current, Mapping) or part not in current:
                return MISSING
            current = current[part]
    return current


def _strict_equal(left: Any, right: Any) -> bool:
    """JS 的 === 对 JSON 原始值的语义：布尔与数字不相等，1 与 1.0 相等。"""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def tool_name_of(event: Mapping[str, Any]) -> str | None:
    data = event.get("data")
    if not isinstance(data, Mapping):
        return None
    function = data.get("function")
    if isinstance(function, Mapping) and isinstance(function.get("name"), str):
        return function["name"]
    name = data.get("name")
    return name if isinstance(name, str) else None


def _as_dict(selector: Any) -> dict[str, Any]:
    if hasattr(selector, "model_dump"):
        selector = selector.model_dump()
    if not isinstance(selector, Mapping):
        raise TypeError("selector 必须是对象或 Selector 模型")
    unknown = set(selector) - set(SELECTOR_FIELDS)
    if unknown:
        raise ValueError(f"selector 包含未知条件：{', '.join(sorted(unknown))}")
    nth = selector.get("nth")
    if nth is not None and (isinstance(nth, bool) or not isinstance(nth, int) or nth < 1):
        raise ValueError(f"selector 的 nth 必须是不小于 1 的整数：{nth!r}")
    return {key: selector.get(key) for key in SELECTOR_FIELDS}


def selector_matches(selector: Any, event: Mapping[str, Any]) -> bool:
    """这一条事件是否满足全部条件；不看 nth（单条事件不知道自己排第几）。"""
    condition = _as_dict(selector)
    if condition["event"] is not None and not _strict_equal(event.get("type"), condition["event"]):
        return False
    if condition["round"] is not None and not _strict_equal(event.get("round"), condition["round"]):
        return False
    if condition["span_kind"] is not None and not _strict_equal(event.get("span_kind"), condition["span_kind"]):
        return False
    if condition["name"] is not None and tool_name_of(event) != condition["name"]:
        return False
    if condition["path"] is not None and resolve_path(event, condition["path"]) is MISSING:
        return False
    return True


def select_events(selector: Any, events: Sequence[Mapping[str, Any]]) -> list[int]:
    """按运行顺序返回所有命中事件的下标；给了 nth 时只剩第 nth 个命中（不够 nth 个就是空）。"""
    condition = _as_dict(selector)
    hits = [index for index, event in enumerate(events) if selector_matches(condition, event)]
    nth = condition["nth"]
    if nth is None:
        return hits
    return hits[nth - 1:nth]


def find_evidence(selector: Any, events: Sequence[Mapping[str, Any]], start: int = 0) -> dict[str, Any]:
    """select_events 选中的事件里，下标不小于 start 的第一条；有 path 时同时返回该路径的值。

    nth 按整次运行数，不从 start 开始数。返回 ``{"found": True, "index": i, "value": v}`` 或
    ``{"found": False}``，与 TS 的 Evidence 相同。
    """
    condition = _as_dict(selector)
    for index in select_events(condition, events):
        if index >= start:
            event = events[index]
            value = resolve_path(event, condition["path"]) if condition["path"] is not None else event
            return {"found": True, "index": index, "value": value}
    return {"found": False}


def count_events(rule: Any, events: Iterable[Mapping[str, Any]]) -> int:
    """predict 的 count_events 规则，与 frontend/src/content/predict.ts 一致：只统计真实运行事件。"""
    if hasattr(rule, "model_dump"):
        rule = rule.model_dump()
    real = [event for event in events if not event.get("provenance") or event.get("provenance") == "real_run"]
    return sum(1 for event in real
               if event.get("type") == rule["event"] and (not rule.get("name") or tool_name_of(event) == rule["name"]))


# 自检场景的测试与内容校验使用的名称。
matches = selector_matches
