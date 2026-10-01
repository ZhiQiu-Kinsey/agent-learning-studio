"""课程内容译文层：按稳定 id 路径合并文本，事实字段不可覆盖。

译文文件放在源文件旁：content.<locale>.json / onboarding.<locale>.json。

    {"schema_version": 1, "locale": "en-US",
     "texts": {"hero.headline": {"text": "...", "source": "<源文本摘要>"}}}

路径规则：带 id 的对象用 id 作为路径段（块 id 在文档内唯一、条目 id 在块内唯一；
没有 id 的输入说明与选项用“列表字段名.name/value”，如 inputs.char_budget.label），
场景、blocks、experiments 等容器不占路径段；没有 id 的子对象用字段名；字符串数组用下标。
只有 Text 类型字段可译；带 x-fact 标记的字段（id、正确答案、练习引用、代码、选择器、URL 等）
和 Literal 字段不可译。source 是译者翻译时源文本的摘要，源文本变化后该条译文视为过期，
回落到源文本并在 stale 中列出。覆盖率在原始译文文件上计算，不受合并结果影响。
"""
from __future__ import annotations

import hashlib
import re
import types
import typing
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

OVERLAY_VERSION = 1
LOCALE = re.compile(r"^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-[A-Z]{2})?$")
# 只组织结构、不承载含义的容器字段。
_TRANSPARENT = {"scenes", "understand", "code", "lab", "check", "blocks", "experiments", "chapters"}


class OverlayError(ValueError):
    pass


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _has_fact(metadata: list[Any]) -> bool:
    return any(isinstance(item, FieldInfo) and isinstance(item.json_schema_extra, dict)
               and item.json_schema_extra.get("x-fact") for item in metadata)


def _text_kind(annotation: Any, metadata: list[Any]) -> str | None:
    """返回 'text'、'list'、'table' 或 None（不可译）。"""
    if _has_fact(metadata):
        return None
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        inner, *extra = typing.get_args(annotation)
        return _text_kind(inner, list(extra))
    if origin in (typing.Union, types.UnionType):
        kinds = {_text_kind(arg, []) for arg in typing.get_args(annotation) if arg is not type(None)}
        return kinds.pop() if len(kinds) == 1 else None
    if annotation is str:
        return "text"
    if origin is list:
        (item,) = typing.get_args(annotation)
        kind = _text_kind(item, [])
        return {"text": "list", "list": "table"}.get(kind or "")
    return None


@dataclass
class Slot:
    container: Any = field(repr=False)
    key: Any

    @property
    def value(self) -> str:
        return self.container[self.key]


def _walk(model: BaseModel, data: dict[str, Any], prefix: str, out: dict[str, Slot]) -> None:
    for name, info in type(model).model_fields.items():
        if info.exclude or name not in data or data[name] is None:
            continue
        value, raw = getattr(model, name), data[name]
        kind = _text_kind(info.annotation, list(info.metadata) + [info])
        if kind == "text":
            out[f"{prefix}{name}"] = Slot(data, name)
        elif kind == "list":
            for index in range(len(raw)):
                out[f"{prefix}{name}.{index}"] = Slot(raw, index)
        elif kind == "table":
            for row, cells in enumerate(raw):
                for column in range(len(cells)):
                    out[f"{prefix}{name}.{row}.{column}"] = Slot(cells, column)
        elif isinstance(value, BaseModel):
            segment = "" if name in _TRANSPARENT else f"{getattr(value, 'id', name)}."
            _walk(value, raw, prefix + segment, out)
        elif isinstance(value, list):
            for index, (item, item_raw) in enumerate(zip(value, raw)):
                if not isinstance(item, BaseModel):
                    continue
                # 稳定键优先：id（全局或块内唯一，直接作路径段）；其次输入字段名 name、选项值 value
                # （只在所属列表内唯一，前面带上列表字段名）；都没有才用下标。
                item_id = getattr(item, "id", None)
                local = next((key for key in (getattr(item, "name", None), getattr(item, "value", None))
                              if isinstance(key, str)), None)
                segment = f"{item_id}." if isinstance(item_id, str) else f"{name}.{local if local else index}."
                _walk(item, item_raw, prefix + segment, out)


def text_slots(model: BaseModel, data: dict[str, Any]) -> dict[str, Slot]:
    """data 必须是 model 的 JSON 形态（model_dump(mode="json")）；返回可译路径到位置的映射。"""
    out: dict[str, Slot] = {}
    _walk(model, data, "", out)
    return out


@dataclass
class Coverage:
    locale: str
    total: int
    translated: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {"locale": self.locale, "total": self.total, "translated": len(self.translated),
                "missing": self.missing, "stale": self.stale}


def validate_overlay(raw: Any, source_texts: dict[str, str], locale: str) -> dict[str, dict[str, str]]:
    """在原始译文文件上校验：结构、语言、只能覆盖可译路径、文本非空。"""
    if not isinstance(raw, dict) or set(raw) - {"$schema", "schema_version", "locale", "texts"}:
        raise OverlayError("译文文件必须是只含 schema_version、locale、texts 的对象")
    if raw.get("schema_version") != OVERLAY_VERSION:
        raise OverlayError(f"译文 schema_version 必须为 {OVERLAY_VERSION}")
    if raw.get("locale") != locale:
        raise OverlayError(f"译文 locale 必须为 {locale}")
    texts = raw.get("texts")
    if not isinstance(texts, dict):
        raise OverlayError("texts 必须是对象")
    for path, entry in texts.items():
        if path not in source_texts:
            raise OverlayError(f"{path} 不是可翻译的文本路径（事实字段或不存在的 id 不能覆盖）")
        if (not isinstance(entry, dict) or set(entry) != {"text", "source"}
                or not isinstance(entry["text"], str) or not entry["text"].strip()
                or not isinstance(entry["source"], str)):
            raise OverlayError(f"{path} 必须是 {{text, source}}，且 text 非空")
    return texts


def coverage(raw: Any, model: BaseModel, data: dict[str, Any], locale: str) -> Coverage:
    slots = text_slots(model, data)
    source_texts = {path: slot.value for path, slot in slots.items()}
    texts = validate_overlay(raw, source_texts, locale)
    result = Coverage(locale=locale, total=len(slots))
    for path, text in source_texts.items():
        entry = texts.get(path)
        if entry is None:
            result.missing.append(path)
        elif entry["source"] != digest(text):
            result.stale.append(path)
        else:
            result.translated.append(path)
    return result


def merge(raw: Any, model: BaseModel, data: dict[str, Any], locale: str) -> Coverage:
    """把有效且未过期的译文写入 data（就地修改），返回覆盖情况。"""
    result = coverage(raw, model, data, locale)
    slots = text_slots(model, data)
    texts = raw["texts"]
    for path in result.translated:
        slot = slots[path]
        slot.container[slot.key] = texts[path]["text"]
    return result
