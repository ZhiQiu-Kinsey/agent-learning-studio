"""检查全部课程实现清单、课程 ID、术语表与随课录制，包含 planned 草稿，不调用模型。"""

import argparse
import json
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
    """译文层：结构与可译路径错误直接失败，缺失与过期只报告覆盖率；课程引用写错也直接失败。

    覆盖课程内容（content.<locale>.json）、导学、课程目录、术语表与各课实现清单（lesson.<locale>.json）。
    """
    from server.content import lesson_content_model, onboarding_model, overlay_locales, overlay_path
    from server.content_overlay import slot_coverage, text_slots
    from server.curriculum import index_catalog
    from server.data_overlay import catalog_slots, glossary_slots, manifest_slots
    from server.glossary import GLOSSARY_FILE, load_glossary
    from server.lesson_refs import check_refs

    root = Path(root).resolve()
    catalog_path = root / "curriculum" / "catalog.json"
    index = index_catalog(json.loads(catalog_path.read_text(encoding="utf-8")))

    def content(model):
        return lambda: text_slots(model, model.model_dump(mode="json", by_alias=True))

    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    documents = [(spec["content_path"], content(lesson_content_model(spec["content_path"], spec))) for spec in specs]
    onboarding = root / "curriculum" / "onboarding.json"
    if onboarding.is_file():
        documents.append((onboarding, content(onboarding_model(onboarding))))
    documents.append((catalog_path, lambda: catalog_slots(read(catalog_path))))
    glossary = root.joinpath(*GLOSSARY_FILE)
    if glossary.is_file():
        documents.append((glossary, lambda: glossary_slots(
            [{**term, "term": term["en"], "local_aliases": []} for term in load_glossary(root, index)["terms"]])))
    for spec in specs:
        manifest = root / "lessons" / spec["module"] / "lesson.json"
        documents.append((manifest, lambda manifest=manifest: manifest_slots(read(manifest))))
    reports = []
    for path, slots in documents:
        for locale in overlay_locales(path):
            overlay = overlay_path(path, locale)
            raw = read(overlay)
            check_refs(raw, index.numbers, str(overlay))
            reports.append((path, slot_coverage(raw, slots(), locale).public()))
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


def english_texts(root, specs):
    """[(文件, 文本路径, 文字, 是否检查 not reported)]：要做英文检查的全部文字，文件是相对 root 的 posix 路径。

    译文层逐条取 texts（数组逐项取）；运行时文本（locales/**/en.py、en.md）整份取；界面文案取 JSON 叶子。
    课程目录只对可运行课程的条目（lesson.<slug>.*）查 not reported，规划中的课与来源说明是计划文字，
    和中文用词检查只看可运行课程一致。
    """
    root = Path(root).resolve()
    available = {spec["id"] for spec in specs if spec.get("status") == "available"}
    out = []

    def relative(path):
        return path.relative_to(root).as_posix()

    def overlay(path, checked=lambda key: True):
        for key, entry in json.loads(path.read_text(encoding="utf-8")).get("texts", {}).items():
            values = entry.get("text") if isinstance(entry, dict) else None
            for value in values if isinstance(values, list) else [values]:
                if isinstance(value, str):
                    out.append((relative(path), key, value, checked(key)))

    for spec in specs:
        folder = root / "lessons" / spec["module"]
        for name in ("content.en.json", "lesson.en.json"):
            if (folder / name).is_file():
                overlay(folder / name)
        locales = folder / "locales"
        if locales.is_dir():
            for path in sorted([*locales.rglob("en.py"), *locales.rglob("en.md")]):
                out.append((relative(path), "*", path.read_text(encoding="utf-8"), True))
    for path in sorted(path for path in (root / "course").rglob("en.py") if "locales" in path.parts):
        out.append((relative(path), "*", path.read_text(encoding="utf-8"), True))
    for path in sorted((root / "curriculum").glob("*.en.json")):
        if path.name == "catalog.en.json":
            overlay(path, lambda key: key.split(".")[0] == "lesson" and key.split(".")[1] in available)
        else:
            overlay(path)
    ui = root / "frontend" / "src" / "i18n" / "locales" / "en"

    def leaves(node, prefix):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from leaves(value, f"{prefix}.{key}" if prefix else key)
        elif isinstance(node, str):
            yield prefix, node

    for path in sorted(ui.glob("*.json")) if ui.is_dir() else []:
        for key, value in leaves(json.loads(path.read_text(encoding="utf-8")), ""):
            out.append((relative(path), key, value, True))
    return out


def validate_english(root, specs):
    """英文文本检查（规则见 server/vocabulary.py 与 terminology.md 第 5 节）。

    返回（[(文件, 文本路径, 类别, 说明)]，[(文件, 文本路径, 子串)] 用不上的白名单条目）。
    用不上的条目只看 root 里确实存在的文件；通配文件（"*"）的条目由 tests/test_english_text.py 在本仓库检查。
    """
    from server.vocabulary import english_problems, unused_allowances

    used = set()
    problems = []
    for file, path, text, unreported in english_texts(root, specs):
        for kind, message in english_problems(file, path, text, used, unreported=unreported):
            problems.append((file, path, kind, message))
    root = Path(root).resolve()
    return problems, unused_allowances(used, lambda file: file != "*" and (root / file).is_file())


DENSITY_BASELINE = ("tests", "baselines", "code-note-density.json")
# 一课只学一件事：术语表里 first_lesson 指向同一课的课程概念不超过这个数。
MAX_NEW_CONCEPTS = 5


def validate_concept_load(root, specs):
    """返回 [(课程, 概念数, 概念名)]：本课引入的课程概念超过上限的课。"""
    from server.catalog import CATALOG_INDEX
    from server.glossary import load_glossary

    terms = load_glossary(Path(root).resolve(), CATALOG_INDEX)["terms"]
    by_lesson = {}
    for term in terms:
        if term.get("kind", "concept") == "concept" and term.get("first_lesson"):
            by_lesson.setdefault(term["first_lesson"], []).append(term["zh"])
    return [(spec["id"], len(by_lesson[spec["id"]]), "、".join(by_lesson[spec["id"]]))
            for spec in specs if len(by_lesson.get(spec["id"], [])) > MAX_NEW_CONCEPTS]


def validate_note_density(root, specs):
    """读码批注密度：返回（不在基线里的问题，已经达标、应从基线删除的块）。基线只许减少。"""
    import json

    from server.code_reading import density_issues
    from server.catalog import _safe_file
    from server.content import lesson_content_model

    root = Path(root).resolve()
    path = root.joinpath(*DENSITY_BASELINE)
    baseline = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    new, fixed = [], []
    for spec in specs:
        model = lesson_content_model(spec["content_path"], spec)
        issues = density_issues(model, lambda relative: _safe_file(root, relative, "sources", source=True)
                                .read_text(encoding="utf-8"))
        allowed = set(baseline.get(spec["id"], []))
        failing = {issue.split("：", 1)[0] for issue in issues}
        new += [(spec["id"], issue) for issue in issues if issue.split("：", 1)[0] not in allowed]
        fixed += [(spec["id"], block) for block in sorted(allowed - failing)]
    return new, fixed


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
            aliases = "、".join(spec.get("aliases", []))
            note = f"（旧 slug：{aliases}）" if aliases else ""
            print(f"  第 {spec['number']} 课 {spec['id']}{note} [{spec['status']}] {spec['title']}")
        print(f"术语表：{terms} 条。" if terms is not None else "术语表：未找到 curriculum/glossary.json，已跳过。")
        if terms is not None:
            problems = validate_vocabulary(args.root, specs)
            print(f"课程用词：{len(problems)} 个问题。")
            if problems:
                for lesson, kind, message in problems:
                    print(f"用词问题 {lesson} [{kind}] {message}", file=sys.stderr)
                print("逐课明细：scripts/term_report.py；规则：docs/architecture/terminology.md", file=sys.stderr)
                return 1
        if terms is not None:
            overloaded = validate_concept_load(args.root, specs)
            print(f"本课新概念：{len(overloaded)} 门课超过 {MAX_NEW_CONCEPTS} 个。")
            if overloaded:
                for lesson, count, names in overloaded:
                    print(f"概念过多 {lesson} {count} 个：{names}（拆课，或挪到前后课）", file=sys.stderr)
                return 1
        density, fixed = validate_note_density(args.root, specs)
        print(f"读码批注密度：{len(density)} 个新问题，{len(fixed)} 个基线块已达标。")
        if density or fixed:
            for lesson, issue in density:
                print(f"批注不足 {lesson} {issue}", file=sys.stderr)
            for lesson, block in fixed:
                print(f"基线可删除 {lesson} {block}（已达标，请从 {'/'.join(DENSITY_BASELINE)} 删掉）", file=sys.stderr)
            return 1
        passed, failures = validate_recordings(args.root, specs)
        print(f"随课录制：{passed} 份通过，{len(failures)} 份未通过。")
        if failures:
            for path, message in failures:
                print(f"录制无效 {path}：{message}", file=sys.stderr)
            return 1
        reports = validate_overlays(args.root, specs)
        print(f"译文层：{len(reports)} 份。")
        for path, report in reports:
            print(f"  {Path(path).relative_to(args.root.resolve()).as_posix()} [{report['locale']}] "
                  f"{report['translated']}/{report['total']}，缺失 {len(report['missing'])}，过期 {len(report['stale'])}")
        english, unused = validate_english(args.root, specs)
        print(f"英文文本：{len(english)} 个问题，{len(unused)} 条用不上的中文白名单。")
        if english or unused:
            for file, path, kind, message in english:
                where = file if path == "*" else f"{file} {path}"
                print(f"英文问题 {where} [{kind}] {message}", file=sys.stderr)
            for file, path, substring in unused:
                print(f"白名单可删除 {file} {path} {substring}（已不再出现，请从 ENGLISH_CJK_ALLOWED 删掉）",
                      file=sys.stderr)
            print("规则：docs/architecture/terminology.md 第 5 节", file=sys.stderr)
            return 1
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
