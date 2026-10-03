"""从课程 JSON 生成可阅读的大纲。

来源是 catalog.json，加上可运行课的 content.json（小节）、lesson.json（是否调用模型）和术语表（本课术语）；
改了其中任何一个都要重新生成。--check 检查文档是否同步。
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.curriculum import index_catalog  # noqa: E402
from server.lesson_refs import resolve_refs  # noqa: E402


def document():
    """课程表文档：catalog 加上可运行课的小节、是否调用模型与本课术语（与 /api/curriculum 相同来源）。"""
    from server.catalog import curriculum_outline

    return render(curriculum_outline(strict=True))


def render(catalog):
    # 显示课号由目录顺序计算；同时完成 slug、别名与先修引用的校验。
    numbers = index_catalog(catalog).numbers
    # 正文里的 {{lesson:<slug>}} 换成按目录顺序计算的“第 N 课”。
    catalog = resolve_refs(catalog, numbers)
    lessons = {item["id"]: item for item in catalog["lessons"]}
    sources = {item["id"]: item for item in catalog["sources"]}

    def label(lesson_id):
        return f"第 {numbers[lesson_id]} 课"

    available = [label(item["id"]) for item in catalog["lessons"] if item["status"] == "available"]
    availability = ("当前可运行课程：" + "、".join(available) + "；其余课程只登记教学计划，后续逐课补充。"
                    if available else "当前课程均为教学计划，尚未开放运行。")
    lines = [f"# {catalog['title']}", "", f"版本：{catalog['version']}。适用环境：Python、多供应商模型接入、本地网页教学平台；百炼是当前已验证配置。", "",
             "> 此文档由 `curriculum/catalog.json` 生成。课程目录、网页和文档使用同一份数据；修改后运行 `python scripts/export_curriculum.py`。", "",
             "> 课号按目录顺序计算，仅用于显示；接口与链接使用课程 ID（slug）。可运行课的小节来自该课正文，规划课的小节是计划。", "",
             "课程按 **大类 → 模块 → 课次 → 知识点 → 实验 → 验收** 组织。" + availability, "",
             "## 学习原则", ""]
    lines.extend(f"- {item}" for item in catalog["principles"])
    lines.extend(["", "## 分类总览", "", "| 大类 | 小模块 | 课号 |", "| --- | --- | --- |"])
    for category in catalog["categories"]:
        ids = [str(numbers[lesson_id]) for module in category["modules"] for lesson_id in module["lesson_ids"]]
        lines.append(f"| {category['title']} | {'；'.join(m['title'] for m in category['modules'])} | {', '.join(ids)} |")
    for category in catalog["categories"]:
        lines.extend(["", f"## {category['id']} · {category['title']}", "", category["description"]])
        for module in category["modules"]:
            lines.extend(["", f"### {module['id']} · {module['title']}", "", module["description"]])
            for lesson_id in module["lesson_ids"]:
                item = lessons[lesson_id]
                state = "已可运行" if item["status"] == "available" else "规划中"
                prerequisites = "、".join(f"{label(p)} {lessons[p]['title']}" for p in item["prerequisites"]) or "Python 函数、字典、异常与 JSON 基础"
                aliases = "、".join(f"`{alias}`" for alias in item.get("aliases", []))
                facts = [f"**层级：** {item['level']}", f"**状态：** {state}"]
                if item.get("difficulty"):
                    facts.append(f"**难度：** {item['difficulty']}")
                if item.get("estimated_minutes"):
                    facts.append(f"**预计：** 约 {item['estimated_minutes']} 分钟")
                calls = item.get("calls_model")
                if calls is not None:
                    facts.append("**模型：** " + ("调用真实模型" if calls else "本课不调用模型"))
                lines.extend(["", f"#### {label(lesson_id)} · {item['title']}", "",
                              f"**课程 ID：** `{lesson_id}`" + (f"（别名 {aliases}）" if aliases else ""), "",
                              "　".join(facts), "",
                              f"**先修：** {prerequisites}", "", item["summary"], ""])
                if item.get("key_terms"):
                    lines.extend(["**本课术语：** " + "、".join(item["key_terms"]), ""])
                if item.get("sections"):
                    lines.extend(["**小节**", ""])
                    lines.extend(f"{i}. **{section['title']}**：{section['gist']}"
                                 for i, section in enumerate(item["sections"], 1))
                    lines.append("")
                lines.extend(["**学习目标**", ""])
                lines.extend(f"- {value}" for value in item["objectives"])
                lines.extend(["", "**知识点与分节**", ""])
                lines.extend(f"- {value}" for value in item["topics"])
                lines.extend(["", "**实验计划**", ""])
                for experiment in item["experiments"]:
                    lines.append(f"{experiment['title']}：")
                    lines.append("")
                    lines.extend(f"{i}. {step}" for i, step in enumerate(experiment["steps"], 1))
                    lines.extend(["", f"产出：{experiment['deliverable']}", ""])
                lines.extend(["**验收要求**", ""])
                lines.extend(f"- {value}" for value in item["acceptance"])
                lines.extend(["", "**参考材料**", ""])
                for reference in item["references"]:
                    source = sources[reference["source"]]
                    lines.append(f"- [{source['title']}]({source['url']})：`{reference['locator']}`。")
    lines.extend(["", "## 选修分支", "", "选修不占用主线课号，根据兴趣与项目需求增加。", ""])
    for item in catalog["electives"]:
        lines.extend([f"### {item['id']} · {item['title']}", "", item["description"], "",
                      "先修：" + "、".join(label(p) for p in item["prerequisites"]), ""])
        lines.extend(f"- {topic}" for topic in item["topics"])
        lines.append("")
    lines.extend(["## 课程参考资料的分工", ""])
    for source in catalog["sources"]:
        lines.extend([f"### [{source['title']}]({source['url']})", "", f"借鉴重点：{source['role']}", "",
                      f"适配取舍：{source['adaptation']}", "", f"参考快照：`{source['commit']}`。", ""])
    next_lesson = next((item for item in catalog["lessons"] if item["status"] == "planned"), None)
    next_step = (f"下一课从{label(next_lesson['id'])}的{next_lesson['title']}开始。" if next_lesson else "当前登记课程均已实现。")
    lines.extend(["## 下一步", "", "先核对目录与课程计划，再按学习进度逐课实现。" + next_step + "计划中课程的具体库版本和框架 API 在制作该课时重新核对。", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = document()
    target = ROOT / "docs/course-plan.md"
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != output:
            raise SystemExit("课程表文档需要更新：python scripts/export_curriculum.py")
        print("Curriculum document is in sync.")
    else:
        target.write_text(output, encoding="utf-8")
        print("Updated docs/course-plan.md")


if __name__ == "__main__":
    main()
