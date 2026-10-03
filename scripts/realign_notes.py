"""源码移动后，把读码块的批注、起止行和折叠区间重新对准到新的行号。

用法：python scripts/realign_notes.py [--check] [--base REV] [课程目录名 ...]
--check 只报告需要移动的地方，不写文件；有要移动的就以非零状态退出。
--base 指定批注当时对应的源码版本（默认 HEAD）。

对准方法：
1. 源码和 --base 版本不同时，按两版源码的逐行对比得到旧行号到新行号的映射。块里每个行号
   （起止、批注、折叠）只要还等于 --base 那一版 content.json 里的值，就按映射移动：在块中间
   插入几行，只有后面的行号跟着变。已经动过的行号（跑过一次或手改过）保持原样，所以连跑
   两次结果不变。
2. 源码和 --base 版本相同（已经提交，或文件是新的）时没有对比可用，退回按锚点：
   批注移到最近的、包含锚点的行；起止行和折叠按相邻批注的位移推算，结果要人工复核。
无论哪种，批注最终都以锚点为准：映射后的行不含锚点时，改找最近的匹配行；找不到或
不唯一时报错，交给作者手动处理。只改 content.json 里的行号，不改批注文字；改完运行
validate_lessons 复核批注密度。
"""
import argparse
import copy
import difflib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.code_reading import split_lines  # noqa: E402


def nearest(lines, anchor, line):
    """离给定行号最近的、包含锚点的行；距离相同的两行同时存在时返回 None（不猜）。"""
    hits = [number for number, text in enumerate(lines, 1) if anchor in text]
    if not hits:
        return None
    hits.sort(key=lambda number: abs(number - line))
    if len(hits) > 1 and abs(hits[0] - line) == abs(hits[1] - line):
        return None
    return hits[0]


class LineMap:
    """旧源码行号 → 新源码行号，按逐行对比的各段推算。

    相同的段一一对应；改写的段（几行换成另外几行）起点落在新段开头、终点落在新段末尾，
    这样改写块末尾几行时，新写的代码仍在块里；删掉的行起点往后找、终点往前找。
    """

    def __init__(self, old_lines, new_lines):
        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        self.segments = [segment for segment in matcher.get_opcodes() if segment[0] != "insert"]
        self.growth = len(new_lines) - len(old_lines)

    def _segment(self, old):
        return next((segment for segment in self.segments if segment[1] < old <= segment[2]), None)

    def start(self, old):
        """区间起点（也用于批注的初始猜测）。"""
        segment = self._segment(old)
        if segment is None:
            return old + self.growth
        tag, i1, _, j1, j2 = segment
        if tag == "equal":
            return j1 + (old - i1)
        if tag == "replace":
            return j1 + 1 + min(old - i1 - 1, j2 - j1 - 1)
        return j1 + 1  # 删掉的行：往后找下一行

    def end(self, old):
        """区间终点。"""
        segment = self._segment(old)
        if segment is None:
            return old + self.growth
        tag, i1, i2, j1, j2 = segment
        if tag == "equal":
            return j1 + (old - i1)
        if tag == "replace":
            return j2 if old == i2 else j1 + 1 + min(old - i1 - 1, j2 - j1 - 1)
        return max(1, j1)  # 删掉的行：往前找上一行


def realign_block(block, lines, mapping=None, base=None):
    """把一个读码块对准到新源码 lines；返回 [(位置, 旧行, 新行)]。无法确定时抛 ValueError。

    mapping 是两版源码的行号映射，base 是 --base 那一版 content.json 里的同一个块。
    有映射时逐个字段判断：行号还等于 base 里的值，说明还没动过，按映射移动；已经不同的
    （跑过一次或作者手改过）保持原样，所以连跑两次结果不变。没有映射时按锚点和相邻批注推算。
    """
    moves = []
    notes = block.get("notes", [])
    old_lines = {note["id"]: note["line"] for note in notes}
    base_notes = {note["id"]: note["line"] for note in (base or {}).get("notes", [])}
    base_folds = {fold["id"]: fold for fold in (base or {}).get("folds", [])}

    def untouched(value, base_value):
        return mapping is not None and base is not None and value == base_value

    for note in notes:
        guess = mapping.start(note["line"]) if untouched(note["line"], base_notes.get(note["id"])) else note["line"]
        if 1 <= guess <= len(lines) and note["anchor"] in lines[guess - 1]:
            target = guess
        else:
            target = nearest(lines, note["anchor"], guess)
        if target is None:
            raise ValueError(f"{block['id']}.{note['id']}：找不到唯一的锚点「{note['anchor']}」")
        if target != note["line"]:
            moves.append((note["id"], note["line"], target))
            note["line"] = target

    # 没有两版源码可比：按相邻批注的位移推算。起点跟后面最近的批注走（多半是上方插入了行），
    # 折叠的起点跟前面最近的批注、终点跟后面最近的批注（折叠里没有批注）。
    points = sorted((old_lines[note["id"]], note["line"] - old_lines[note["id"]]) for note in notes)

    def shift_before(line):
        before = [shift for old, shift in points if old <= line]
        return before[-1] if before else (points[0][1] if points else 0)

    def shift_after(line):
        after = [shift for old, shift in points if old >= line]
        return after[0] if after else (points[-1][1] if points else 0)

    def place(value, base_value, kind, inside_fold=False):
        if mapping is not None and base is not None:
            if value != base_value:
                return value  # 已经动过：保持原样
            return mapping.start(value) if kind == "start" else mapping.end(value)
        if inside_fold:
            if kind == "start":
                return value + (shift_before(value) if any(old < value for old, _ in points) else shift_after(value))
            return value + (shift_after(value) if any(old > value for old, _ in points) else shift_before(value))
        return value + (shift_after(value) if kind == "start" else shift_before(value))

    for key in ("start", "end"):
        if block.get(key):
            new = max(1, min(len(lines), place(block[key], (base or {}).get(key), key)))
            if new != block[key]:
                moves.append((key, block[key], new))
                block[key] = new
    for fold in block.get("folds", []):
        base_fold = base_folds.get(fold["id"], {})
        for key in ("start", "end"):
            new = max(1, min(len(lines), place(fold[key], base_fold.get(key), key, inside_fold=True)))
            if new != fold[key]:
                moves.append((f"{fold['id']}.{key}", fold[key], new))
                fold[key] = new
    noted = [note["line"] for note in notes]
    if noted and block.get("start") and block["start"] > min(noted):
        moves.append(("start", block["start"], min(noted)))
        block["start"] = min(noted)
    if noted and block.get("end") and block["end"] < max(noted):
        moves.append(("end", block["end"], max(noted)))
        block["end"] = max(noted)
    return moves


def git_show(path, base):
    """--base 版本里的文件内容；取不到（新文件、不在 git 里）时返回 None。"""
    try:
        return subprocess.run(["git", "show", f"{base}:{path}"], cwd=ROOT, capture_output=True,
                              check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return None


def mapping_for(old_lines, new_lines):
    """源码和 --base 版本不同时返回两版的行号映射，否则返回 None。"""
    if old_lines is None or old_lines == new_lines:
        return None
    return LineMap(old_lines, new_lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lessons", nargs="*", help="只处理这些课程目录（如 lesson_05_structured_output）")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--base", default="HEAD", help="批注当时对应的源码版本（默认 HEAD）")
    args = parser.parse_args(argv)
    try:
        subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}"], cwd=ROOT,
                       capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        print(f"--base {args.base} 不是有效的提交，未做任何改动。", file=sys.stderr)
        return 2
    paths = sorted((ROOT / "lessons").glob("*/content.json"))
    if args.lessons:
        paths = [path for path in paths if path.parent.name in args.lessons]
    failed = False
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        base_text = git_show(path.relative_to(ROOT).as_posix(), args.base)
        base_blocks = {}
        if base_text is not None:
            base_data = json.loads(base_text)
            base_blocks = {block["id"]: block for block in (base_data.get("scenes", {}).get("code") or {})
                           .get("blocks", []) if block.get("type") == "annotated-source"}
        changed, broken = False, False
        blocks = (data.get("scenes", {}).get("code") or {}).get("blocks", [])
        for index, block in enumerate(blocks):
            if block.get("type") != "annotated-source":
                continue
            lines = split_lines((ROOT / block["path"]).read_text(encoding="utf-8"))
            old_text = git_show(block["path"], args.base)
            mapping = mapping_for(split_lines(old_text) if old_text is not None else None, lines)
            # 在副本上对准，整块成功才替换：一条批注找不到锚点时，不留下移了一半的块。
            candidate = copy.deepcopy(block)
            try:
                moves = realign_block(candidate, lines, mapping, base_blocks.get(block["id"]))
            except ValueError as error:
                print(f"{path.parent.name}：{error}", file=sys.stderr)
                failed = broken = True
                continue
            blocks[index] = candidate
            how = "按两版源码对比" if mapping and block["id"] in base_blocks else "按锚点推算，请复核起止行与折叠"
            for where, old_line, new_line in moves:
                print(f"{path.parent.name} {block['id']}.{where}：{old_line} → {new_line}（{how}）")
            changed = changed or bool(moves)
        if broken:
            print(f"{path.parent.name}：有块无法对准，这个文件没有写入。", file=sys.stderr)
            continue
        if changed and args.check:
            failed = True  # --check：有要移动的也算没通过，留给作者去跑一次不带 --check 的命令
        elif changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
