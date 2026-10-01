"""读取并校验课程内容与导学（content v2）。

旧版本文件先在内存中走迁移阶梯再校验；磁盘文件由 scripts/migrate_content.py 负责升级。
返回值补齐了 Pydantic 声明的默认值，前端拿到的是完整结构。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from server.content_migrations import LESSON_STEPS, ONBOARDING_STEPS, ContentVersionError, migrate
from server.content_overlay import LOCALE, OverlayError, coverage, merge, text_slots
from server.content_schema import LessonContent, Onboarding
from server.curriculum import LessonValidationError


def _describe(error: ValidationError, limit: int = 5) -> str:
    parts = []
    for item in error.errors()[:limit]:
        where = ".".join(str(part) for part in item["loc"]) or "<root>"
        parts.append(f"{where}: {item['msg']}")
    more = len(error.errors()) - limit
    return "；".join(parts) + (f"；另有 {more} 处" if more > 0 else "")


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LessonValidationError(f"{path}: 无法读取 JSON（{error}）") from None
    if not isinstance(data, dict):
        raise LessonValidationError(f"{path}: 必须是 JSON 对象")
    return data


def _public(model) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)


def overlay_path(path: Path, locale: str) -> Path:
    return path.with_name(f"{path.stem}.{locale}.json")


def _localize(path: Path, model, data: dict[str, Any], locale: str | None) -> dict[str, Any]:
    """合并译文层并返回本次实际使用的语言与缺失情况；译文损坏时回落到源语言。"""
    source = model.source_language
    total = len(text_slots(model, data))
    info: dict[str, Any] = {"requested": locale or source, "locale": source, "source_language": source,
                            "total": total, "translated": 0, "missing": [], "stale": []}
    if not locale or locale == source:
        info["translated"] = total
        return info
    file = overlay_path(path, locale)
    if not file.is_file():
        info["missing"] = list(text_slots(model, data))
        return info
    try:
        result = merge(_read(file), model, data, locale)
    except (OverlayError, LessonValidationError) as error:
        info["missing"] = list(text_slots(model, data))
        info["error"] = str(error)
        return info
    return {**info, **result.public(), "locale": locale if result.translated else source}


def overlay_report(path: Path, model, locale: str) -> dict[str, Any]:
    """校验脚本使用：在原始译文文件上计算覆盖率，结构错误直接抛出。"""
    data = _public(model)
    return coverage(_read(overlay_path(path, locale)), model, data, locale).public()


def overlay_locales(path: Path) -> list[str]:
    prefix = path.stem + "."
    return sorted(file.name[len(prefix):-5] for file in path.parent.glob(f"{path.stem}.*.json")
                  if LOCALE.fullmatch(file.name[len(prefix):-5]))


def lesson_content_model(path: Path, lesson: dict[str, Any]) -> LessonContent:
    """lesson 需要 id、subtitle、exercises（来自已校验的 lesson.json）。"""
    context = {"lesson": lesson["id"], "subtitle": lesson["subtitle"], "exercises": lesson["exercises"]}
    try:
        model = LessonContent.model_validate(migrate(_read(path), LESSON_STEPS, context))
    except ContentVersionError as error:
        raise LessonValidationError(f"{path}: {error}") from None
    except ValidationError as error:
        raise LessonValidationError(f"{path}: {_describe(error)}") from None
    if model.lesson != lesson["id"]:
        raise LessonValidationError(f"{path}: lesson 必须为 {lesson['id']}")
    exercise_ids = {exercise["id"] for exercise in lesson["exercises"]}
    for experiment in model.scenes.lab.experiments if model.scenes.lab else []:
        for arm in experiment.arms:
            if arm.exercise not in exercise_ids:
                raise LessonValidationError(f"{path}: 实验 {experiment.id} 引用了不存在的练习 {arm.exercise}")
    return model


def load_lesson_content(path: Path, lesson: dict[str, Any], locale: str | None = None
                        ) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回（内容, 语言信息）。"""
    model = lesson_content_model(path, lesson)
    data = _public(model)
    return data, _localize(path, model, data, locale)


def onboarding_model(path: Path) -> Onboarding:
    try:
        return Onboarding.model_validate(migrate(_read(path), ONBOARDING_STEPS))
    except ContentVersionError as error:
        raise LessonValidationError(f"{path}: {error}") from None
    except ValidationError as error:
        raise LessonValidationError(f"{path}: {_describe(error)}") from None


def load_onboarding(path: Path, locale: str | None = None) -> dict[str, Any]:
    model = onboarding_model(path)
    data = _public(model)
    return {**data, "i18n": _localize(path, model, data, locale)}
