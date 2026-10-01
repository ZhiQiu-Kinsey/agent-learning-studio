"""课程内容的迁移阶梯。

每一步只升一个版本，都是纯函数 (data, context) -> data；找不到路径直接报错；
比代码新的内容原样不动并报错，由调用方提示升级平台。学习记录的版本线在前端独立维护。
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from .content_schema import CONTENT_VERSION

Context = Mapping[str, Any]
Step = Callable[[dict[str, Any], Context], dict[str, Any]]


class ContentVersionError(ValueError):
    pass


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64].strip("-") or fallback


def _items(texts: list[str], prefix: str) -> list[dict[str, str]]:
    return [{"id": f"{prefix}-{index}", "text": text} for index, text in enumerate(texts, 1)]


def _question(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _slug(item["id"], "question"),
        "prompt": item["prompt"],
        "options": [{"id": _slug(option["id"], "option"), "text": option["text"]}
                    for option in item["options"]],
        "correct": _slug(item["correct_option"], "option"),
        "explanation": item["explanation"],
    }


def lesson_v1_to_v2(data: dict[str, Any], context: Context) -> dict[str, Any]:
    """v1：sections/observe/quiz/presentation → v2 场景结构。

    context 需要 lesson（slug）、subtitle 与 exercises（lesson.json 中的练习）。
    """
    understand: list[dict[str, Any]] = []
    presentation = data.get("presentation")
    if presentation:
        understand.append({
            "type": "hero", "id": "hero",
            "eyebrow": presentation["eyebrow"], "headline": presentation["headline"],
            "highlight": presentation["highlight"], "takeaway": presentation["takeaway"],
        })
        concepts = []
        for index, concept in enumerate(presentation["concepts"], 1):
            concepts.append({"id": _slug(concept["label"], f"concept-{index}"), **{
                key: concept[key] for key in ("label", "title", "description", "token")}})
        if concepts:
            understand.append({"type": "concepts", "id": "concepts", "items": concepts})
    for index, section in enumerate(data["sections"], 1):
        understand.append({"type": "prose", "id": f"section-{index}",
                           "title": section["title"], "paragraphs": [section["body"]]})
    if presentation:
        flow = presentation["flow"]
        understand.append({
            "type": "walkthrough", "id": "walkthrough",
            "title": flow["title"], "description": flow["description"],
            "steps": [{"id": f"step-{index}", **{key: step[key] for key in (
                "label", "actor", "title", "body", "code", "language", "evidence")}}
                for index, step in enumerate(flow["steps"], 1)],
        })

    exercises = context["exercises"]
    if not exercises:
        raise ContentVersionError("迁移实验需要 lesson.json 中至少一个练习")
    experiment = {
        "id": "explore",
        "title": context["subtitle"],
        "arms": [{"id": _slug(exercise["id"], f"arm-{index}"), "exercise": exercise["id"],
                  "label": exercise["title"]} for index, exercise in enumerate(exercises, 1)],
        "observe": [{"id": f"observe-{index}", "text": text}
                    for index, text in enumerate(data["observe"], 1)],
    }
    return {
        "schema_version": 2,
        "lesson": context["lesson"],
        "source_language": "zh-CN",
        "scenes": {
            "understand": {"blocks": understand},
            "lab": {"experiments": [experiment]},
            "check": {"blocks": [{"type": "quiz", "id": "quiz",
                                  "questions": [_question(item) for item in data["quiz"]]}]},
        },
    }


def _section_block(section: dict[str, Any]) -> dict[str, Any]:
    kind, identifier = section["kind"], _slug(section["id"], "section")
    paragraphs = section.get("paragraphs", [])
    if kind == "explanation":
        return {"type": "prose", "id": identifier, "title": section["title"],
                "paragraphs": paragraphs}
    if kind == "steps":
        return {"type": "steps", "id": identifier, "title": section["title"],
                "paragraphs": paragraphs, "items": _items(section["bullets"], "item")}
    if kind == "comparison":
        return {"type": "compare", "id": identifier, "title": section["title"],
                "paragraphs": paragraphs, "columns": section["table"]["columns"],
                "rows": section["table"]["rows"]}
    if kind == "warning":
        return {"type": "callout", "id": identifier, "tone": "warning",
                "title": section["title"], "paragraphs": paragraphs}
    raise ContentVersionError(f"未知的导学段落类型：{kind}")


def onboarding_v1_to_v2(data: dict[str, Any], _context: Context) -> dict[str, Any]:
    chapters = []
    for chapter in sorted(data["chapters"], key=lambda item: item["order"]):
        understand = [{"type": "objectives", "id": "objectives",
                       "items": _items(chapter["learning_objectives"], "objective")}]
        understand += [_section_block(section) for section in chapter["sections"]]
        if chapter.get("references"):
            understand.append({"type": "references", "id": "references", "items": [
                {"id": f"ref-{index}", "title": ref["title"], "url": ref["url"]}
                for index, ref in enumerate(chapter["references"], 1)]})
        exercise = chapter["exercise"]
        chapters.append({
            "id": chapter["id"], "title": chapter["title"], "eyebrow": chapter["eyebrow"],
            "summary": chapter["summary"], "estimated_minutes": chapter["estimated_minutes"],
            "next_label": chapter.get("next_label"),
            "scenes": {
                "understand": {"blocks": understand},
                "check": {"blocks": [{"type": "checkpoint", "id": "exercise",
                                      "title": exercise["title"], "prompt": exercise["prompt"],
                                      "items": _items(exercise["checkpoints"], "checkpoint")}]},
            },
        })
    return {"schema_version": 2, "source_language": "zh-CN", "title": data["title"],
            "description": data["description"], "chapters": chapters}


LESSON_STEPS: dict[int, Step] = {1: lesson_v1_to_v2}
ONBOARDING_STEPS: dict[int, Step] = {1: onboarding_v1_to_v2}


def _version(data: dict[str, Any]) -> int:
    # v1 课程内容没有版本字段；v1 导学使用 version。
    value = data.get("schema_version", data.get("version", 1))
    if type(value) is not int or value < 1:
        raise ContentVersionError(f"无法识别的内容版本：{value!r}")
    return value


def migrate(data: dict[str, Any], steps: Mapping[int, Step], context: Context | None = None,
            target: int = CONTENT_VERSION) -> dict[str, Any]:
    version = _version(data)
    if version > target:
        raise ContentVersionError(f"内容版本 {version} 比平台支持的 {target} 新，请先升级平台")
    while version < target:
        step = steps.get(version)
        if step is None:
            raise ContentVersionError(f"没有从版本 {version} 升到 {version + 1} 的迁移")
        data = step(data, context or {})
        version += 1
        if _version(data) != version:
            raise ContentVersionError(f"迁移步骤 {version - 1} 没有产出版本 {version}")
    return data
