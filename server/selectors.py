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
SELECTOR_FIELDS = ("event", "round", "path", "span_kind", "name")


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
    return {key: selector.get(key) for key in SELECTOR_FIELDS}


def selector_matches(selector: Any, event: Mapping[str, Any]) -> bool:
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
    """按运行顺序返回所有命中事件的下标。"""
    return [index for index, event in enumerate(events) if selector_matches(selector, event)]


def find_evidence(selector: Any, events: Sequence[Mapping[str, Any]], start: int = 0) -> dict[str, Any]:
    """从 start（含）开始找第一条命中事件；有 path 时同时返回该路径的值。

    返回 ``{"found": True, "index": i, "value": v}`` 或 ``{"found": False}``，与 TS 的 Evidence 相同。
    """
    condition = _as_dict(selector)
    for index in range(max(0, start), len(events)):
        event = events[index]
        if selector_matches(condition, event):
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
