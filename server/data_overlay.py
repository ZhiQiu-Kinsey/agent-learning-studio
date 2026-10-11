"""课程目录、术语表与实现清单的译文层路径。

文件格式、摘要与回落规则同 content_overlay：译文放在源文件旁（catalog.en.json、glossary.en.json、
lessons/*/lesson.en.json），``{"schema_version": 1, "locale": "en", "texts": {路径: {text, source}}}``。
这三类文件不是 Pydantic 模型，可译路径在这里逐类列出；路径一律以 id 为键（课程 slug、大类/模块/
选修/参考资料 id、术语 id、练习 id），只有没有 id 的字符串数组和实验用下标。
id、slug、状态、先修、课时、难度、URL、提交号、练习问题与预设输入都是事实，不在可译路径里：
练习问题和预设输入会原样发给模型，属于运行事实，界面切到英文时也保持源语言。
"""
from __future__ import annotations

from typing import Any

from server.content_overlay import Slot


def _texts(out: dict[str, Slot], prefix: str, owner: dict[str, Any], fields: tuple[str, ...]) -> None:
    for name in fields:
        if isinstance(owner.get(name), str) and owner[name].strip():
            out[f"{prefix}{name}"] = Slot(owner, name)


def _list(out: dict[str, Slot], prefix: str, owner: dict[str, Any], name: str) -> None:
    values = owner.get(name)
    if isinstance(values, list):
        for index, value in enumerate(values):
            if isinstance(value, str) and value.strip():
                out[f"{prefix}{name}.{index}"] = Slot(values, index)


def catalog_slots(catalog: dict[str, Any]) -> dict[str, Slot]:
    """catalog.json 中网页、课程地图与课程表显示的文本。

    路径：title、principles.<n>、category.<id>.title|description、module.<id>.title|description、
    lesson.<slug>.title|summary|objectives.<n>|topics.<n>|acceptance.<n>|experiments.<n>.title|
    experiments.<n>.steps.<m>|experiments.<n>.deliverable|sections.<n>.title|sections.<n>.gist、
    elective.<id>.title|description|topics.<n>、source.<id>.role|adaptation。
    可运行课的小节来自 content.json 的译文层，这里只有规划课写在目录里的小节。
    """
    out: dict[str, Slot] = {}
    _texts(out, "", catalog, ("title",))
    _list(out, "", catalog, "principles")
    for category in catalog.get("categories", []):
        _texts(out, f"category.{category['id']}.", category, ("title", "description"))
        for module in category.get("modules", []):
            _texts(out, f"module.{module['id']}.", module, ("title", "description"))
    for lesson in catalog.get("lessons", []):
        prefix = f"lesson.{lesson['id']}."
        _texts(out, prefix, lesson, ("title", "summary"))
        for name in ("objectives", "topics", "acceptance"):
            _list(out, prefix, lesson, name)
        for index, experiment in enumerate(lesson.get("experiments", [])):
            _texts(out, f"{prefix}experiments.{index}.", experiment, ("title", "deliverable"))
            _list(out, f"{prefix}experiments.{index}.", experiment, "steps")
        for index, section in enumerate(lesson.get("sections", [])):
            _texts(out, f"{prefix}sections.{index}.", section, ("title", "gist"))
    for elective in catalog.get("electives", []):
        _texts(out, f"elective.{elective['id']}.", elective, ("title", "description"))
        _list(out, f"elective.{elective['id']}.", elective, "topics")
    for source in catalog.get("sources", []):
        _texts(out, f"source.{source['id']}.", source, ("role", "adaptation"))
    return out


def glossary_slots(terms: list[dict[str, Any]]) -> dict[str, Slot]:
    """术语表：每个术语的显示名 term、definition 与该语言的别名 aliases。

    terms 是公开条目（已带 term 与 local_aliases 字段）。中英映射（id、zh、en、first_lesson、kind）
    不可译。term 与 aliases 的源文本是英文名 en：英文名改了，显示名和英文别名一起过期；
    aliases 的译文是字符串数组，写进 local_aliases，源文件里的中文别名保持不变（中文正文仍按它匹配）。
    """
    out: dict[str, Slot] = {}
    for term in terms:
        prefix = f"{term['id']}."
        out[prefix + "term"] = Slot(term, "term", source=term["en"])
        out[prefix + "definition"] = Slot(term, "definition")
        out[prefix + "aliases"] = Slot(term, "local_aliases", source=term["en"], kind="list")
    return out


def manifest_slots(manifest: dict[str, Any]) -> dict[str, Slot]:
    """lesson.json 中界面显示的文本：subtitle、exercises.<id>.title、ui.question_label、ui.question_help。

    课程标题、简介与学习目标来自 catalog.json；练习的 question 与 inputs 原样发给模型，不可译。
    """
    out: dict[str, Slot] = {}
    _texts(out, "", manifest, ("subtitle",))
    for exercise in manifest.get("exercises", []):
        _texts(out, f"exercises.{exercise['id']}.", exercise, ("title",))
    ui = manifest.get("ui")
    if isinstance(ui, dict):
        _texts(out, "ui.", ui, ("question_label", "question_help"))
    return out
