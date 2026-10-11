"""课程译文层工具：导出待译文本、写回译文并自动记录源文本摘要。

    python scripts/translation_kit.py list
    python scripts/translation_kit.py export <目标> --locale en [--all] [-o file.json]
    python scripts/translation_kit.py apply  <目标> --locale en -i translated.json [--check]
    python scripts/translation_kit.py status --locale en

目标：lesson:<slug>（content.json）、onboarding（curriculum/onboarding.json）、
catalog（curriculum/catalog.json）、glossary（curriculum/glossary.json）、manifest:<slug>（lesson.json）。
各类文件的可译路径见 server/content_overlay.py 与 server/data_overlay.py。
export 输出 {路径: 源文本}；默认只导出缺失或过期的条目，--all 导出全部。
apply 读入 {路径: 译文}，与已有译文层合并后整体校验再写回；占位符（{{...}}）与行内代码（`...`）
必须与源文本一致，否则拒绝写入，避免译文破坏课程引用和代码名。
术语的 <id>.aliases 译文是字符串数组（该语言的别名，没有时写 []），导出时的源文本是术语的英文名。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.content_overlay import OVERLAY_VERSION, Slot, digest, slot_coverage, text_slots  # noqa: E402

_PLACEHOLDER = re.compile(r"\{\{[^{}]+\}\}")
_CODE = re.compile(r"`[^`\n]+`")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _content_slots(build: Callable[[], Any]) -> Callable[[], dict[str, Slot]]:
    def slots() -> dict[str, Slot]:
        model = build()
        return text_slots(model, model.model_dump(mode="json", by_alias=True))
    return slots


def _glossary_slots() -> dict[str, Slot]:
    from server.catalog import CATALOG_INDEX
    from server.data_overlay import glossary_slots
    from server.glossary import load_glossary

    terms = [{**term, "term": term["en"], "local_aliases": []}
             for term in load_glossary(ROOT, CATALOG_INDEX)["terms"]]
    return glossary_slots(terms)


def _documents() -> dict[str, tuple[Path, Callable[[], dict[str, Slot]]]]:
    """目标名 -> (源文件, 返回可译位置的函数)；源文件先经过与网页相同的校验。"""
    from server.catalog import load_lessons
    from server.content import lesson_content_model, onboarding_model
    from server.curriculum import CATALOG_PATH
    from server.data_overlay import catalog_slots, manifest_slots

    specs = load_lessons(root=ROOT, include_planned=True)
    docs: dict[str, tuple[Path, Callable[[], dict[str, Slot]]]] = {}
    for spec in specs:
        path = spec["content_path"]
        docs[f"lesson:{spec['id']}"] = (path, _content_slots(lambda path=path, spec=spec: lesson_content_model(path, spec)))
    onboarding = ROOT / "curriculum" / "onboarding.json"
    docs["onboarding"] = (onboarding, _content_slots(lambda: onboarding_model(onboarding)))
    docs["catalog"] = (CATALOG_PATH, lambda: catalog_slots(_read_json(CATALOG_PATH)))
    docs["glossary"] = (ROOT / "curriculum" / "glossary.json", _glossary_slots)
    for spec in specs:
        manifest = ROOT / "lessons" / spec["module"] / "lesson.json"
        docs[f"manifest:{spec['id']}"] = (manifest, lambda manifest=manifest: manifest_slots(_read_json(manifest)))
    return docs


def _overlay_file(path: Path, locale: str) -> Path:
    return path.with_name(f"{path.stem}.{locale}.json")


def _read_overlay(path: Path, locale: str) -> dict[str, Any]:
    file = _overlay_file(path, locale)
    if file.is_file():
        return _read_json(file)
    return {"schema_version": OVERLAY_VERSION, "locale": locale, "texts": {}}


def _tokens(pattern: re.Pattern[str], text: str) -> list[str]:
    return sorted(pattern.findall(text))


def check_entry(path: str, source: str, text: str) -> list[str]:
    problems = []
    if not text.strip():
        problems.append(f"{path}: 译文为空")
    if _tokens(_PLACEHOLDER, source) != _tokens(_PLACEHOLDER, text):
        problems.append(f"{path}: 占位符与源文本不一致 {_tokens(_PLACEHOLDER, source)}")
    if _tokens(_CODE, source) != _tokens(_CODE, text):
        problems.append(f"{path}: 行内代码与源文本不一致 {_tokens(_CODE, source)}")
    return problems


def check_value(path: str, slot: Slot, value: Any) -> list[str]:
    if slot.kind == "list":
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            return [f"{path}: 译文必须是字符串数组（没有别的叫法时写 []）"]
        return []
    if not isinstance(value, str):
        return [f"{path}: 译文必须是字符串"]
    return check_entry(path, slot.value, value)


def export(target: str, locale: str, include_all: bool) -> dict[str, str]:
    path, build = _documents()[target]
    sources = {key: slot.value for key, slot in build().items()}
    if include_all:
        return sources
    texts = _read_overlay(path, locale)["texts"]
    return {key: value for key, value in sources.items()
            if key not in texts or texts[key]["source"] != digest(value)}


def apply(target: str, locale: str, translations: dict[str, Any], dry_run: bool = False) -> Path:
    path, build = _documents()[target]
    slots = build()
    problems = [f"{key}: 不是可翻译路径" for key in translations if key not in slots]
    for key, value in translations.items():
        if key in slots:
            problems += check_value(key, slots[key], value)
    if problems:
        raise SystemExit("拒绝写入：\n" + "\n".join(problems))
    overlay = _read_overlay(path, locale)
    for key, value in translations.items():
        overlay["texts"][key] = {"text": value, "source": digest(slots[key].value)}
    # 按源文件中的顺序写出，方便审阅时对照。
    overlay["texts"] = {key: overlay["texts"][key] for key in slots if key in overlay["texts"]}
    slot_coverage(overlay, slots, locale)
    file = _overlay_file(path, locale)
    if dry_run:
        return file
    file.write_bytes((json.dumps(overlay, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return file


def status(locale: str) -> list[tuple[str, int, int, int]]:
    rows = []
    for target, (path, build) in _documents().items():
        report = slot_coverage(_read_overlay(path, locale), build(), locale)
        rows.append((target, report.total, len(report.translated), len(report.stale)))
    return rows


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("export", "apply"):
        command = sub.add_parser(name)
        command.add_argument("target")
        command.add_argument("--locale", required=True)
    sub.choices["export"].add_argument("--all", action="store_true")
    sub.choices["export"].add_argument("-o", "--output")
    sub.choices["apply"].add_argument("-i", "--input", required=True)
    sub.choices["apply"].add_argument("--check", action="store_true", help="只校验，不写文件")
    sub.add_parser("status").add_argument("--locale", required=True)
    args = parser.parse_args(argv)

    if args.command == "list":
        print("\n".join(_documents()))
    elif args.command == "export":
        text = json.dumps(export(args.target, args.locale, args.all), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_bytes(text.encode("utf-8"))
        else:
            sys.stdout.buffer.write(text.encode("utf-8"))
    elif args.command == "apply":
        translations = _read_json(Path(args.input))
        file = apply(args.target, args.locale, translations, dry_run=args.check)
        verb = "校验通过（未写入）" if args.check else "已写入"
        print(f"{verb} {file.relative_to(ROOT)}（{len(translations)} 条）")
    else:
        for target, total, done, stale in status(args.locale):
            print(f"{target:40} {done:4}/{total:<4} 过期 {stale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
