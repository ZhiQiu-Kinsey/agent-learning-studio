"""检查全部课程实现清单、课程 ID、术语表与随课录制，包含 planned 草稿，不调用模型。"""

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def validate(root):
    # 放在函数中，导入时的配置错误也能在 CLI 中显示为开发诊断。
    from server.catalog import load_lessons

    return load_lessons(root=Path(root).resolve(), include_planned=True)


def validate_glossary(root):
    """术语表存在时校验 id、必填字段与课程引用；返回条目数，缺少文件时返回 None。"""
    from server.catalog import _json
    from server.curriculum import index_catalog
    from server.glossary import GLOSSARY_FILE, load_glossary

    root = Path(root).resolve()
    if not root.joinpath(*GLOSSARY_FILE).is_file():
        return None
    index = index_catalog(_json(root / "curriculum" / "catalog.json"))
    return len(load_glossary(root, index)["terms"])


def validate_recordings(root, specs):
    """随课录制（lessons/*/recordings/）的完整校验；规则见 server/recordings.py。"""
    from scripts.validate_recordings import collect

    return collect(root, specs)


def validate_overlays(root, specs):
    """内容译文层：结构与可译路径错误直接失败，缺失与过期只报告覆盖率。"""
    from server.content import lesson_content_model, onboarding_model, overlay_locales, overlay_report

    documents = [(spec["content_path"], lesson_content_model(spec["content_path"], spec)) for spec in specs]
    onboarding = Path(root) / "curriculum" / "onboarding.json"
    if onboarding.is_file():
        documents.append((onboarding, onboarding_model(onboarding)))
    reports = []
    for path, model in documents:
        for locale in overlay_locales(path):
            reports.append((path, overlay_report(path, model, locale)))
    return reports


def validate_vocabulary(root, specs):
    """可运行课程的用词检查（术语、中英并列、裸英文词、代码说明）；返回 [(课程, 类别, 说明)]。"""
    from server.catalog import CATALOG_INDEX, lesson_code_names
    from server.content import lesson_content_model
    from server.glossary import load_glossary
    from server.vocabulary import lesson_problems

    terms = load_glossary(Path(root).resolve(), CATALOG_INDEX)["terms"]
    runnable = [spec for spec in specs if spec.get("status") == "available"]
    available = {spec["id"] for spec in runnable}
    problems = []
    for spec in runnable:
        model = lesson_content_model(spec["content_path"], spec)
        for kind, message in lesson_problems(spec["id"], model, terms, CATALOG_INDEX.numbers,
                                             lesson_code_names(spec), available):
            problems.append((spec["id"], kind, message))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="包含 curriculum/catalog.json 的项目根目录")
    args = parser.parse_args(argv)
    try:
        specs = validate(args.root)
        terms = validate_glossary(args.root)
        available = sum(spec.get("status") == "available" for spec in specs)
        print(f"校验通过：{len(specs)} 份课程实现清单（{available} 可用，{len(specs) - available} 规划草稿）。")
        for spec in specs:
            aliases = "、".join(spec.get("aliases", [])) or "无"
            print(f"  第 {spec['number']} 课 {spec['id']}（别名：{aliases}）[{spec['status']}] {spec['title']}")
        print(f"术语表：{terms} 条。" if terms is not None else "术语表：未找到 curriculum/glossary.json，已跳过。")
        if terms is not None:
            problems = validate_vocabulary(args.root, specs)
            print(f"课程用词：{len(problems)} 个问题。")
            if problems:
                for lesson, kind, message in problems:
                    print(f"用词问题 {lesson} [{kind}] {message}", file=sys.stderr)
                print("逐课明细：scripts/term_report.py；规则：docs/architecture/terminology.md", file=sys.stderr)
                return 1
        passed, failures = validate_recordings(args.root, specs)
        print(f"随课录制：{passed} 份通过，{len(failures)} 份未通过。")
        if failures:
            for path, message in failures:
                print(f"录制无效 {path}：{message}", file=sys.stderr)
            return 1
        reports = validate_overlays(args.root, specs)
        print(f"内容译文层：{len(reports)} 份。")
        for path, report in reports:
            print(f"  {Path(path).relative_to(args.root.resolve()).as_posix()} [{report['locale']}] "
                  f"{report['translated']}/{report['total']}，缺失 {len(report['missing'])}，过期 {len(report['stale'])}")
        print("未调用模型；结构校验不代替课程测试与教学验收，planned 课程不会因此解锁。")
        return 0
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        print(f"课程校验失败（项目：{args.root.resolve()}）：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
