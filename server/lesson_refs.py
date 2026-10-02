"""正文里的课程引用：作者写 ``{{lesson:<slug>}}``，后端读取时按目录顺序换成“第 N 课”。

显示课号由 catalog 的目录顺序计算，插入新课会让后面的课号整体后移，正文里写死的数字会过期。
所以课程内容、导学和课程目录里提到另一门课时写 slug，课号在读取时计算；未登记的 slug 在校验时报错。
源码与运行事件不经过这里：它们是真实数据，不做替换。
"""
from __future__ import annotations

import re
from typing import Any

from server.curriculum import LessonValidationError

REF = re.compile(r"\{\{lesson:([^{}]*)\}\}")
TEMPLATES = {"zh-CN": "第 {number} 课", "en-US": "Lesson {number}"}


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def lesson_refs(value: Any) -> list[str]:
    """按出现顺序列出引用的 slug（可重复）。"""
    return [match.group(1) for text in _strings(value) for match in REF.finditer(text)]


def check_refs(value: Any, numbers: dict[str, int], location: str) -> None:
    """每个引用都必须指向目录中已登记的课程 slug。"""
    for slug in lesson_refs(value):
        if slug not in numbers:
            raise LessonValidationError(f"{location}: 课程引用 {{{{lesson:{slug}}}}} 指向未登记的课程")


def render_ref(slug: str, numbers: dict[str, int], locale: str | None = None) -> str:
    template = TEMPLATES.get(locale or "zh-CN", TEMPLATES["zh-CN"])
    return template.format(number=numbers[slug]) if slug in numbers else slug


def resolve_refs(value: Any, numbers: dict[str, int], locale: str | None = None) -> Any:
    """返回替换后的副本；未登记的 slug 原样留下 slug（校验会先拦住它）。"""
    if isinstance(value, str):
        return REF.sub(lambda match: render_ref(match.group(1), numbers, locale), value)
    if isinstance(value, dict):
        return {key: resolve_refs(item, numbers, locale) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_refs(item, numbers, locale) for item in value]
    return value
