"""源码移动后，按锚点把读码批注重新对准到最近的匹配行，并按同样的位移调整块的起止行。

用法：python scripts/realign_notes.py [--check] [课程目录名 ...]
--check 只报告需要移动的批注，不写文件。找不到锚点或最近的匹配不唯一时报错，交给作者手动处理。
只改 content.json 里的行号，不改批注文字；改完运行 validate_lessons 复核。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.code_reading import split_lines  # noqa: E402


def nearest(lines, anchor, line):
    """离原行号最近的、包含锚点的行；距离相同的两行同时存在时返回 None（不猜）。"""
    hits = [number for number, text in enumerate(lines, 1) if anchor in text]
    if not hits:
        return None
    hits.sort(key=lambda number: abs(number - line))
    if len(hits) > 1 and abs(hits[0] - line) == abs(hits[1] - line):
        return None
    return hits[0]


def realign_block(block, lines):
    """返回 [(批注 id, 旧行, 新行)]；无法确定时抛 ValueError。"""
    moves = []
    for note in block.get("notes", []):
        if note["line"] <= len(lines) and note["anchor"] in lines[note["line"] - 1]:
            continue
        target = nearest(lines, note["anchor"], note["line"])
        if target is None:
            raise ValueError(f"{block['id']}.{note['id']}：找不到唯一的锚点「{note['anchor']}」")
        moves.append((note["id"], note["line"], target))
        note["line"] = target
    if moves:
        shifts = sorted(new - old for _, old, new in moves)
        shift = shifts[len(shifts) // 2]
        for key in ("start", "end"):
            if block.get(key):
                block[key] = max(1, min(len(lines), block[key] + shift))
        for fold in block.get("folds", []):
            fold["start"] += shift
            fold["end"] += shift
        noted = [note["line"] for note in block["notes"]]
        if block.get("start"):
            block["start"] = min(block["start"], *noted)
        if block.get("end"):
            block["end"] = max(block["end"], *noted)
    return moves


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lessons", nargs="*", help="只处理这些课程目录（如 lesson_05_structured_output）")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    paths = sorted((ROOT / "lessons").glob("*/content.json"))
    if args.lessons:
        paths = [path for path in paths if path.parent.name in args.lessons]
    failed = False
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for block in (data.get("scenes", {}).get("code") or {}).get("blocks", []):
            if block.get("type") != "annotated-source":
                continue
            lines = split_lines((ROOT / block["path"]).read_text(encoding="utf-8"))
            try:
                moves = realign_block(block, lines)
            except ValueError as error:
                print(f"{path.parent.name}：{error}", file=sys.stderr)
                failed = True
                continue
            for note_id, old, new in moves:
                print(f"{path.parent.name} {block['id']}.{note_id}：{old} → {new}")
            changed = changed or bool(moves)
        if changed and not args.check:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
