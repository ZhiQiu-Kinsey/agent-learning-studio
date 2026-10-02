r"""逐课列出用词：本课引入、回顾和背景术语，带说明的代码名，以及要处理的问题。

    .\.venv\Scripts\python.exe scripts/term_report.py                 # 全部课程，只列问题
    .\.venv\Scripts\python.exe scripts/term_report.py --lesson task-contract --full

中文术语是否该收录，机器判断不了；--full 会列出本课所有被标注的词，供作者通读正文时对照
（规则见 docs/architecture/terminology.md）。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.catalog import CATALOG_INDEX, LESSONS, ROOT, lesson_code_names  # noqa: E402
from server.content import lesson_content_model  # noqa: E402
from server.glossary import load_glossary  # noqa: E402
from server.vocabulary import TermMatcher, lesson_problems, marked_texts  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lesson", help="课程 slug；不填则检查全部课程")
    parser.add_argument("--full", action="store_true", help="同时列出本课标注的术语与代码说明")
    args = parser.parse_args()
    terms = load_glossary(ROOT, CATALOG_INDEX)["terms"]
    numbers = CATALOG_INDEX.numbers
    available = {spec["id"] for spec in LESSONS}
    specs = [spec for spec in LESSONS if args.lesson in (None, spec["id"])]
    if not specs:
        parser.error(f"没有可运行的课程 {args.lesson}")
    total = 0
    for spec in specs:
        model = lesson_content_model(spec["content_path"], spec)
        names = lesson_code_names(spec)
        problems = lesson_problems(spec["id"], model, terms, numbers, names, available)
        total += len(problems)
        if not problems and not args.full:
            continue
        print(f"\n第 {numbers[spec['id']]} 课 {spec['id']}：{len(problems)} 个问题")
        if args.full:
            matcher = TermMatcher(terms)
            hits = matcher.first_hits("\n".join(marked_texts(model)))
            by_id = {term["id"]: term for term in terms}
            groups = {"本课引入": [], "回顾": [], "背景": []}
            for term_id in hits:
                term = by_id[term_id]
                key = ("背景" if term.get("kind") == "background"
                       else "本课引入" if term.get("first_lesson") == spec["id"] else "回顾")
                groups[key].append(term["zh"])
            for key, values in groups.items():
                print(f"  {key}：{'、'.join(values) or '无'}")
            notes = "、".join(item.name for item in model.code_notes) or "无"
            print(f"  带说明的代码名：{notes}")
        for kind, message in problems:
            print(f"  [{kind}] {message}")
    print(f"\n共 {total} 个问题。")
    return 1 if total else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
