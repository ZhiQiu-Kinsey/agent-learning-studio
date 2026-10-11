"""从课程 JSON 生成可阅读的大纲：中文 docs/course-plan.md，英文 docs/course-plan.en.md。

来源是 catalog.json，加上可运行课的 content.json（小节）、lesson.json（是否调用模型）和术语表（本课术语）；
英文版用各自的译文层（catalog.en.json、content.en.json、glossary.en.json），缺的条目回落到中文。
改了其中任何一个都要重新生成。--check 检查文档是否同步；--locale 只处理一种语言（默认两种都处理）。
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.curriculum import index_catalog  # noqa: E402
from server.lesson_refs import resolve_refs, template_for  # noqa: E402

TARGETS = {"zh-CN": "docs/course-plan.md", "en": "docs/course-plan.en.md"}

# 文档里的固定文字。层级与难度按代码取（level_code、difficulty_code），与网页的翻译一致。
LABELS = {
    "zh-CN": {
        "version": "版本：{version}。适用环境：Python、多供应商模型接入、本地网页教学平台；百炼是当前已验证配置。",
        "generated": "> 此文档由 `curriculum/catalog.json` 生成。课程目录、网页和文档使用同一份数据；修改后运行 `python scripts/export_curriculum.py`。",
        "numbers": "> 课号按目录顺序计算，仅用于显示；接口与链接使用课程 ID（slug）。可运行课的小节来自该课正文，规划课的小节是计划。",
        "structure": "课程按 **大类 → 模块 → 课次 → 知识点 → 实验 → 验收** 组织。",
        "available": "当前可运行课程：{lessons}；其余课程只登记教学计划，后续逐课补充。",
        "none_available": "当前课程均为教学计划，尚未开放运行。",
        "list": "、", "modules": "；", "colon": "：", "space": "　",
        "principles": "## 学习原则", "overview": "## 分类总览",
        "overview_head": "| 大类 | 小模块 | 课号 |",
        "state": {"available": "已可运行", "planned": "规划中"},
        "default_prerequisites": "Python 函数、字典、异常与 JSON 基础",
        "id": "**课程 ID：** `{id}`", "aliases": "（别名 {aliases}）",
        "level": "**层级：** {value}", "status": "**状态：** {value}", "difficulty": "**难度：** {value}",
        "minutes": "**预计：** 约 {value} 分钟", "model": "**模型：** {value}",
        "calls_model": "调用真实模型", "no_model": "本课不调用模型",
        "prerequisites": "**先修：** {value}", "terms": "**本课术语：** {value}",
        "sections": "**小节**", "objectives": "**学习目标**", "topics": "**知识点与分节**",
        "experiments": "**实验计划**", "deliverable": "产出：{value}", "acceptance": "**验收要求**",
        "references": "**参考材料**",
        "electives": "## 选修分支", "electives_intro": "选修不占用主线课号，根据兴趣与项目需求增加。",
        "elective_prerequisites": "先修：{value}",
        "sources": "## 课程参考资料的分工", "role": "借鉴重点：{value}", "adaptation": "适配取舍：{value}",
        "snapshot": "参考快照：`{value}`。",
        "next": "## 下一步",
        "next_lesson": "下一课从{label}的{title}开始。", "all_done": "当前登记课程均已实现。",
        "next_text": "先核对目录与课程计划，再按学习进度逐课实现。{next}计划中课程的具体库版本和框架 API 在制作该课时重新核对。",
        "level_codes": {"core": "必修", "advanced": "进阶", "elective": "选修"},
        "difficulty_codes": {"beginner": "入门", "intermediate": "进阶", "challenge": "挑战"},
    },
    "en": {
        "version": "Version: {version}. Environment: Python, multi-provider model access, a local web learning platform; Bailian is the currently verified configuration.",
        "generated": "> Generated from `curriculum/catalog.json` and its English overlays. The catalog, the web pages and this document share one source; after a change run `python scripts/export_curriculum.py`. Text without an English translation yet is shown in Chinese.",
        "numbers": "> Lesson numbers follow catalog order and are for display only; the API and links use the lesson ID (slug). Sections of available lessons come from their lesson text; sections of planned lessons are plans.",
        "structure": "The course is organized as **category → module → lesson → topics → experiments → acceptance**.",
        "available": "Available now: {lessons}. The other lessons are registered as plans and will be added one by one.",
        "none_available": "All lessons are plans; none can be run yet.",
        "list": ", ", "modules": "; ", "colon": ": ", "space": " · ",
        "principles": "## Learning principles", "overview": "## Overview by category",
        "overview_head": "| Category | Modules | Lessons |",
        "state": {"available": "Available", "planned": "Planned"},
        "default_prerequisites": "Python functions, dicts, exceptions and JSON basics",
        "id": "**Lesson ID:** `{id}`", "aliases": " (aliases {aliases})",
        "level": "**Level:** {value}", "status": "**Status:** {value}", "difficulty": "**Difficulty:** {value}",
        "minutes": "**Time:** about {value} min", "model": "**Model:** {value}",
        "calls_model": "calls a real model", "no_model": "no model calls",
        "prerequisites": "**Prerequisites:** {value}", "terms": "**Terms in this lesson:** {value}",
        "sections": "**Sections**", "objectives": "**Objectives**", "topics": "**Topics**",
        "experiments": "**Experiments**", "deliverable": "Deliverable: {value}", "acceptance": "**Acceptance**",
        "references": "**References**",
        "electives": "## Electives", "electives_intro": "Electives have no main-line lesson number; add them as your interests and projects need.",
        "elective_prerequisites": "Prerequisites: {value}",
        "sources": "## What each reference contributes", "role": "What we borrow: {value}",
        "adaptation": "How we adapt it: {value}", "snapshot": "Reference snapshot: `{value}`.",
        "next": "## Next",
        "next_lesson": "The next lesson is {label}, {title}.", "all_done": "Every registered lesson is implemented.",
        "next_text": "Check the catalog and the plan first, then implement lessons in learning order. {next} Library versions and framework APIs of planned lessons are checked again when each lesson is built.",
        "level_codes": {"core": "Core", "advanced": "Advanced", "elective": "Elective"},
        "difficulty_codes": {"beginner": "Beginner", "intermediate": "Intermediate", "challenge": "Challenge"},
    },
}


def document(locale="zh-CN"):
    """课程表文档：catalog 加上可运行课的小节、是否调用模型与本课术语（与 /api/curriculum 相同来源）。"""
    from server.catalog import curriculum_outline

    return render(curriculum_outline(strict=True, locale=None if locale == "zh-CN" else locale), locale)


def render(catalog, locale="zh-CN"):
    text = LABELS[locale]
    # 显示课号由目录顺序计算；同时完成 slug、别名与先修引用的校验。
    numbers = index_catalog(catalog).numbers
    # 正文里的 {{lesson:<slug>}} 换成按目录顺序计算的课号（译文层已按目标语言换好，其余按中文写）。
    catalog = resolve_refs(catalog, numbers)
    lessons = {item["id"]: item for item in catalog["lessons"]}
    sources = {item["id"]: item for item in catalog["sources"]}
    join = text["list"].join

    def label(lesson_id):
        return template_for(locale).format(number=numbers[lesson_id])

    def coded(item, field):
        code = item.get(field + "_code")
        return text[field + "_codes"].get(code, item.get(field)) if code else item.get(field)

    available = [label(item["id"]) for item in catalog["lessons"] if item["status"] == "available"]
    availability = text["available"].format(lessons=join(available)) if available else text["none_available"]
    lines = [f"# {catalog['title']}", "", text["version"].format(version=catalog["version"]), "",
             text["generated"], "", text["numbers"], "",
             text["structure"] + ("" if locale == "zh-CN" else " ") + availability, "",
             text["principles"], ""]
    lines.extend(f"- {item}" for item in catalog["principles"])
    lines.extend(["", text["overview"], "", text["overview_head"], "| --- | --- | --- |"])
    for category in catalog["categories"]:
        ids = [str(numbers[lesson_id]) for module in category["modules"] for lesson_id in module["lesson_ids"]]
        lines.append(f"| {category['title']} | {text['modules'].join(m['title'] for m in category['modules'])} "
                     f"| {', '.join(ids)} |")
    for category in catalog["categories"]:
        lines.extend(["", f"## {category['id']} · {category['title']}", "", category["description"]])
        for module in category["modules"]:
            lines.extend(["", f"### {module['id']} · {module['title']}", "", module["description"]])
            for lesson_id in module["lesson_ids"]:
                item = lessons[lesson_id]
                prerequisites = (join(f"{label(p)} {lessons[p]['title']}" for p in item["prerequisites"])
                                 or text["default_prerequisites"])
                aliases = join(f"`{alias}`" for alias in item.get("aliases", []))
                facts = [text["level"].format(value=coded(item, "level")),
                         text["status"].format(value=text["state"][item["status"]])]
                if item.get("difficulty"):
                    facts.append(text["difficulty"].format(value=coded(item, "difficulty")))
                if item.get("estimated_minutes"):
                    facts.append(text["minutes"].format(value=item["estimated_minutes"]))
                calls = item.get("calls_model")
                if calls is not None:
                    facts.append(text["model"].format(value=text["calls_model"] if calls else text["no_model"]))
                lines.extend(["", f"#### {label(lesson_id)} · {item['title']}", "",
                              text["id"].format(id=lesson_id) + (text["aliases"].format(aliases=aliases)
                                                                 if aliases else ""), "",
                              text["space"].join(facts), "",
                              text["prerequisites"].format(value=prerequisites), "", item["summary"], ""])
                if item.get("key_terms"):
                    lines.extend([text["terms"].format(value=join(item["key_terms"])), ""])
                if item.get("sections"):
                    lines.extend([text["sections"], ""])
                    lines.extend(f"{i}. **{section['title']}**{text['colon']}{section['gist']}"
                                 for i, section in enumerate(item["sections"], 1))
                    lines.append("")
                lines.extend([text["objectives"], ""])
                lines.extend(f"- {value}" for value in item["objectives"])
                lines.extend(["", text["topics"], ""])
                lines.extend(f"- {value}" for value in item["topics"])
                lines.extend(["", text["experiments"], ""])
                for experiment in item["experiments"]:
                    lines.append(f"{experiment['title']}{text['colon'].rstrip()}")
                    lines.append("")
                    lines.extend(f"{i}. {step}" for i, step in enumerate(experiment["steps"], 1))
                    lines.extend(["", text["deliverable"].format(value=experiment["deliverable"]), ""])
                lines.extend([text["acceptance"], ""])
                lines.extend(f"- {value}" for value in item["acceptance"])
                lines.extend(["", text["references"], ""])
                for reference in item["references"]:
                    source = sources[reference["source"]]
                    lines.append(f"- [{source['title']}]({source['url']}){text['colon']}`{reference['locator']}`"
                                 + ("。" if locale == "zh-CN" else "."))
    lines.extend(["", text["electives"], "", text["electives_intro"], ""])
    for item in catalog["electives"]:
        lines.extend([f"### {item['id']} · {item['title']}", "", item["description"], "",
                      text["elective_prerequisites"].format(value=join(label(p) for p in item["prerequisites"])), ""])
        lines.extend(f"- {topic}" for topic in item["topics"])
        lines.append("")
    lines.extend([text["sources"], ""])
    for source in catalog["sources"]:
        lines.extend([f"### [{source['title']}]({source['url']})", "", text["role"].format(value=source["role"]), "",
                      text["adaptation"].format(value=source["adaptation"]), "",
                      text["snapshot"].format(value=source["commit"]), ""])
    next_lesson = next((item for item in catalog["lessons"] if item["status"] == "planned"), None)
    next_step = (text["next_lesson"].format(label=label(next_lesson["id"]), title=next_lesson["title"])
                 if next_lesson else text["all_done"])
    lines.extend([text["next"], "", text["next_text"].format(next=next_step), ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--locale", choices=sorted(TARGETS), help="只处理这一种语言；默认两种都处理")
    args = parser.parse_args()
    stale = []
    for locale in [args.locale] if args.locale else list(TARGETS):
        output = document(locale)
        target = ROOT / TARGETS[locale]
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != output:
                stale.append(TARGETS[locale])
        else:
            target.write_text(output, encoding="utf-8")
            print(f"Updated {TARGETS[locale]}")
    if args.check:
        if stale:
            raise SystemExit("课程表文档需要更新（" + "、".join(stale) + "）：python scripts/export_curriculum.py")
        print("Curriculum documents are in sync.")


if __name__ == "__main__":
    main()
