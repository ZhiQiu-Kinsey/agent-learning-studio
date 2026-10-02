"""声明式事件选择器的 Python 实现，语义与 frontend/src/content/selector.ts 一致。

观察点、导览和轨迹找错共用同一套选择器；后端用它在确定性运行中校验内容里的目标
能否命中。两边的语义由共享测试向量 frontend/src/content/__fixtures__/selector-vectors.json
约束，修改任一侧都要同时更新向量。
"""
from __future__ import annotations

import re
from typing import Any

# 与 selector.ts 的 /[^.[\]]+|\[\d+\]/g 相同：点号分隔的键，或方括号里的非负整数下标。
_PATH_PART = re.compile(r"[^.\[\]]+|\[\d+\]")


class _Missing:
    """对应 JS 的 undefined；JSON 里的 null 是存在的值，不能与它混用。"""

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


def resolve_path(value: Any, path: str) -> Any:
    """按 data.body.choices[0].message 这样的路径取值；路径不存在时返回 MISSING，不推测。"""
    parts = _PATH_PART.findall(path)
    if not parts:
        return MISSING
    current = value
    for part in parts:
        if current is None or current is MISSING:
            return MISSING
        if part.startswith("["):
            # bool 是 int 的子类，但 JSON 里的数组只会是 list。
            if not isinstance(current, list):
                return MISSING
            index = int(part[1:-1])
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            if not isinstance(current, dict) or part not in current:
                return MISSING
            current = current[part]
    return current


def _strict_equal(left: Any, right: Any) -> bool:
    """JS 的 === ：类型不同就不相等（Python 里 True == 1，这里必须区分）。"""
    if left is MISSING or right is MISSING:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def tool_name_of(event: dict) -> str | None:
    """工具名：tool_call 在 data.function.name，tool_result 在 data.name。"""
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    function = data.get("function")
    if isinstance(function, dict) and isinstance(function.get("name"), str):
        return function["name"]
    name = data.get("name")
    return name if isinstance(name, str) else None


def matches(selector: dict, event: dict) -> bool:
    """选择器的每个非空条件都满足才算命中；path 只要求该路径存在（值可以是 null）。"""
    expected = selector.get("event")
    if expected is not None and not _strict_equal(event.get("type", MISSING), expected):
        return False
    expected = selector.get("round")
    if expected is not None and not _strict_equal(event.get("round", MISSING), expected):
        return False
    expected = selector.get("span_kind")
    if expected is not None and not _strict_equal(event.get("span_kind", MISSING), expected):
        return False
    expected = selector.get("name")
    if expected is not None and tool_name_of(event) != expected:
        return False
    path = selector.get("path")
    if path is not None and resolve_path(event, path) is MISSING:
        return False
    return True


def select_events(selector: dict, events: list[dict]) -> list[int]:
    """按运行顺序返回命中事件的下标。"""
    return [index for index, event in enumerate(events) if matches(selector, event)]
