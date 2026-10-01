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


def load_lesson_content(path: Path, lesson: dict[str, Any]) -> dict[str, Any]:
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
    return _public(model)


def load_onboarding(path: Path) -> dict[str, Any]:
    try:
        return _public(Onboarding.model_validate(migrate(_read(path), ONBOARDING_STEPS)))
    except ContentVersionError as error:
        raise LessonValidationError(f"{path}: {error}") from None
    except ValidationError as error:
        raise LessonValidationError(f"{path}: {_describe(error)}") from None
