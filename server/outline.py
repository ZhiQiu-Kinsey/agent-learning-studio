"""课程表细纲：预计时长、难度、小节、是否调用模型、本课术语。

- 预计时长与难度写在 catalog 每课条目里（estimated_minutes、difficulty）。
- 可运行课的小节从 content.json 理解场景的正文节导出，“是否调用模型”读 lesson.json，二者不在 catalog 重复维护；
  规划课还没有内容，小节与 calls_model 由作者写在 catalog 条目里。
- 本课术语是术语表里 first_lesson 为本课的课程概念。
"""
from __future__ import annotations

import re
from typing import Any

from server.curriculum import _require

DIFFICULTIES = ("入门", "进阶", "挑战")
_SENTENCE = re.compile(r"^(.+?[。！？])")
GIST_MAX = 80


def check_details(entry: dict[str, Any], where: str) -> None:
    """校验 catalog 条目里的细纲字段；字段可省略（测试用的最小目录没有它们），出现时必须合法。"""
    minutes = entry.get("estimated_minutes")
    if minutes is not None:
        _require(type(minutes) is int and 5 <= minutes <= 600, where + ".estimated_minutes", "必须是 5–600 的整数分钟")
    difficulty = entry.get("difficulty")
    if difficulty is not None:
        _require(difficulty in DIFFICULTIES, where + ".difficulty", "必须是 " + "、".join(DIFFICULTIES) + " 之一")
    planned = entry.get("status") == "planned"
    if "sections" in entry:
        _require(planned, where + ".sections", "可运行课的小节由 content.json 导出，catalog 里只给规划课写小节")
        sections = entry["sections"]
        _require(isinstance(sections, list) and 2 <= len(sections) <= 10, where + ".sections", "必须是 2–10 项的数组")
        for section in sections:
            _require(isinstance(section, dict) and set(section) == {"title", "gist"}
                     and all(isinstance(section[key], str) and section[key].strip() for key in ("title", "gist")),
                     where + ".sections", "每项只能有非空的 title 与 gist")
    if "calls_model" in entry:
        _require(planned, where + ".calls_model", "可运行课是否调用模型由 lesson.json 的 requires_model 决定")
        _require(type(entry["calls_model"]) is bool, where + ".calls_model", "必须是布尔值")


def _gist(paragraphs: list[str]) -> str:
    text = (paragraphs or [""])[0].strip()
    match = _SENTENCE.match(text)
    sentence = match.group(1) if match else text
    return sentence if len(sentence) <= GIST_MAX else sentence[:GIST_MAX - 1] + "…"


def content_sections(learning: dict[str, Any]) -> list[dict[str, str]]:
    """理解场景里每个正文节的标题与第一句话。"""
    blocks = (learning.get("scenes", {}).get("understand") or {}).get("blocks", [])
    return [{"title": block["title"], "gist": _gist(block.get("paragraphs", []))}
            for block in blocks if block.get("type") == "prose" and block.get("title")]


def lesson_terms(terms: list[dict[str, Any]]) -> dict[str, list[str]]:
    """{课程 slug: [本课引入的课程概念显示名]}；公开术语（public_glossary）带好了所选语言的 display。"""
    from server.glossary import display_label

    result: dict[str, list[str]] = {}
    for term in terms:
        if term.get("kind", "concept") == "concept" and term.get("first_lesson"):
            result.setdefault(term["first_lesson"], []).append(term.get("display") or display_label(term))
    return result


def enrich(catalog: dict[str, Any], specs: list[dict[str, Any]], learning_of, terms: list[dict[str, Any]]
           ) -> dict[str, Any]:
    """给课程表每课补上 sections、calls_model、key_terms；learning_of(spec) 返回该课 content 输出。"""
    by_id = {spec["id"]: spec for spec in specs}
    introduced = lesson_terms(terms)
    for lesson in catalog["lessons"]:
        spec = by_id.get(lesson["id"])
        if spec is not None and lesson.get("status") == "available":
            lesson["sections"] = content_sections(learning_of(spec))
            lesson["calls_model"] = bool(spec["runtime"]["requires_model"])
        else:
            lesson.setdefault("sections", [])
            lesson.setdefault("calls_model", None)
        lesson["key_terms"] = introduced.get(lesson["id"], [])
    return catalog
