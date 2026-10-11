"""正文里的课程引用：作者写 ``{{lesson:<slug>}}``，后端读取时按目录顺序换成“第 N 课”。

显示课号由 catalog 的目录顺序计算，插入新课会让后面的课号整体后移，正文里写死的数字会过期。
所以课程内容、导学、实现清单和课程目录里提到另一门课时写 slug，课号在读取时计算；
未登记的 slug 和写错格式的引用（如 ``{{ lesson:x }}``、少一个括号）在加载时就报错。
源码与运行事件不经过这里：它们是真实数据，不做替换。
"""
from __future__ import annotations

import re
from typing import Any

from server.curriculum import LessonValidationError

REF = re.compile(r"\{\{lesson:([^{}]*)\}\}")
# 像引用却没写对的：多了空格、少了一个括号、大写 L、中文冒号。正文里的 JSON 和代码示例
# 本身会有 “}}” 和 {lesson: …}，不能一概拦，所以要求括号里是一个 slug。
LOOSE = re.compile(r"\{\s*\{?\s*lesson\s*[:：]\s*[a-z0-9-]+\s*\}?\s*\}", re.IGNORECASE)
# 多了一个括号：替换后会残留一个 “{” 或 “}”。
EXTRA = re.compile(r"\{\{\{lesson:|\{\{lesson:[^{}]*\}\}\}")
# 按语言（不分地区）选模板：en 与 en-US 都写 “Lesson N”；未知语言用源语言写法。
TEMPLATES = {"zh": "第 {number} 课", "en": "Lesson {number}"}


def template_for(locale: str | None) -> str:
    return TEMPLATES.get((locale or "zh-CN").split("-")[0].lower(), TEMPLATES["zh"])


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
    """每个引用都必须指向目录中已登记的课程 slug；写错格式的引用直接报错。"""
    for slug in lesson_refs(value):
        if slug not in numbers:
            raise LessonValidationError(f"{location}: 课程引用 {{{{lesson:{slug}}}}} 指向未登记的课程")
    for text in _strings(value):
        if LOOSE.search(REF.sub("", text)) or EXTRA.search(text):
            # 写错的引用不会被替换，会原样出现在网页上；这里直接拦下。
            raise LessonValidationError(f"{location}: 课程引用格式不对（应写 {{{{lesson:<slug>}}}}）：{text[:60]}")


def render_ref(slug: str, numbers: dict[str, int], locale: str | None = None) -> str:
    """未登记的 slug 直接报错：加载时已校验，走到这里说明有文件绕过了校验，不能把 slug 当课号显示。"""
    if slug not in numbers:
        raise LessonValidationError(f"课程引用 {{{{lesson:{slug}}}}} 指向未登记的课程")
    return template_for(locale).format(number=numbers[slug])


def resolve_refs(value: Any, numbers: dict[str, int], locale: str | None = None) -> Any:
    """返回替换后的副本。"""
    if isinstance(value, str):
        return REF.sub(lambda match: render_ref(match.group(1), numbers, locale), value)
    if isinstance(value, dict):
        return {key: resolve_refs(item, numbers, locale) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_refs(item, numbers, locale) for item in value]
    return value
