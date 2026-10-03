"""scripts/realign_notes.py：源码插删行后，批注、块起止和折叠区间只按实际位置移动。"""
import copy
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from realign_notes import LineMap, mapping_for, realign_block  # noqa: E402

OLD = [f"line {number}" for number in range(1, 13)]
BLOCK = {"id": "code-x", "start": 2, "end": 10,
         "notes": [{"id": "n3", "line": 3, "anchor": "line 3"}, {"id": "n8", "line": 8, "anchor": "line 8"}],
         "folds": [{"id": "fold", "start": 5, "end": 6, "label": "平台代码"}]}


def realign(new, mapping=True):
    block = copy.deepcopy(BLOCK)
    if mapping:
        realign_block(block, new, LineMap(OLD, new), BLOCK)
    else:
        realign_block(block, new, None)
    return block


def shape(block):
    return (block["start"], block["end"], [note["line"] for note in block["notes"]],
            [(fold["start"], fold["end"]) for fold in block["folds"]])


class RealignTests(unittest.TestCase):
    def test_lines_inserted_inside_a_block_only_move_what_comes_after(self):
        # 在第 3 行（批注）和折叠之间插入两行：起点和前面的批注不动，折叠、后面的批注和终点后移。
        new = OLD[:3] + ["new a", "new b"] + OLD[3:]
        self.assertEqual(shape(realign(new)), (2, 12, [3, 10], [(7, 8)]))

    def test_lines_inserted_inside_a_fold_stretch_the_fold(self):
        new = OLD[:5] + ["new"] + OLD[5:]
        self.assertEqual(shape(realign(new)), (2, 11, [3, 9], [(5, 7)]))

    def test_lines_inserted_above_the_block_move_everything(self):
        new = ["import x", "import y"] + OLD
        self.assertEqual(shape(realign(new)), (4, 12, [5, 10], [(7, 8)]))

    def test_deleted_boundary_lines_snap_inside_the_range(self):
        # 删掉块的第一行和折叠的最后一行：起点落到下一行，折叠终点落到上一行。
        new = OLD[:1] + OLD[2:5] + OLD[6:]
        self.assertEqual(shape(realign(new)), (2, 8, [2, 6], [(4, 4)]))

    def test_anchor_wins_when_the_mapped_line_lost_it(self):
        new = list(OLD)
        new[7] = "line 8 changed"  # 锚点仍在原行
        block = realign(new)
        self.assertEqual(block["notes"][1]["line"], 8)
        new[7], new[8] = "rewritten", "line 8 moved here"
        self.assertEqual(realign(new)["notes"][1]["line"], 9)

    def test_without_a_base_version_shifts_follow_the_neighbouring_notes(self):
        # 没有两版源码可比时按锚点推算：上方插入的行让整块一起后移。
        new = ["import x", "import y"] + OLD
        self.assertEqual(shape(realign(new, mapping=False)), (4, 12, [5, 10], [(7, 8)]))

    def test_rewriting_the_last_lines_keeps_the_new_code_inside_the_block(self):
        # 块的最后一行改写成三行：终点落在新段末尾，新代码仍在块里。
        grown = OLD[:9] + ["total = a + b", "print(total)", "return total"] + OLD[10:]
        self.assertEqual(realign(grown)["end"], 12)
        # 反过来，两行合成一行：终点落在合并后的那一行。
        shrunk = OLD[:8] + ["merged"] + OLD[10:]
        self.assertEqual(realign(shrunk)["end"], 9)

    def test_running_twice_does_not_move_anything_again(self):
        new = OLD[:3] + ["new a", "new b"] + OLD[3:]
        first = copy.deepcopy(BLOCK)
        realign_block(first, new, mapping_for(OLD, new), BLOCK)
        self.assertEqual(shape(first), (2, 12, [3, 10], [(7, 8)]))
        # 第二次：动过的行号不再等于 --base 的值，保持原样；没动过的映射后也不变。
        second = copy.deepcopy(first)
        self.assertEqual(realign_block(second, new, mapping_for(OLD, new), BLOCK), [])
        self.assertEqual(shape(second), shape(first))

    def test_hand_moved_notes_still_let_the_ranges_follow_the_source(self):
        # 上方插入两行，作者只手改了批注：起止和折叠仍等于 --base 的值，照样按映射移动。
        new = ["import x", "import y"] + OLD
        block = copy.deepcopy(BLOCK)
        for note in block["notes"]:
            note["line"] += 2
        realign_block(block, new, mapping_for(OLD, new), BLOCK)
        self.assertEqual(shape(block), (4, 12, [5, 10], [(7, 8)]))

    def test_no_mapping_when_the_source_did_not_change(self):
        self.assertIsNone(mapping_for(OLD, list(OLD)))
        self.assertIsNone(mapping_for(None, OLD))

    def test_missing_or_ambiguous_anchor_is_an_error(self):
        new = [text for text in OLD if text != "line 8"]
        with self.assertRaisesRegex(ValueError, "找不到唯一的锚点"):
            realign(new)




class RealignScriptTests(unittest.TestCase):
    """在临时 git 仓库里跑 main()：对准、--check、连跑两次、写错的 --base、锚点失效时不写文件。"""

    def setUp(self):
        import json
        import subprocess
        import tempfile
        import realign_notes
        self.json, self.module = json, realign_notes
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        lesson = self.root / "lessons" / "lesson_x"
        lesson.mkdir(parents=True)
        (lesson / "src.py").write_text("\n".join(OLD) + "\n", encoding="utf-8")
        block = {"type": "annotated-source", "path": "lessons/lesson_x/src.py", **copy.deepcopy(BLOCK)}
        self.content = lesson / "content.json"
        self.content.write_text(json.dumps({"scenes": {"code": {"blocks": [block]}}}), encoding="utf-8")
        self.git = lambda *args: subprocess.run(["git", *args], cwd=self.root, capture_output=True, check=True)
        self.git("init", "-q")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "base")
        self.root_patch = patch.object(realign_notes, "ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def run_main(self, *argv):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.module.main(list(argv))

    def block(self):
        return self.json.loads(self.content.read_text(encoding="utf-8"))["scenes"]["code"]["blocks"][0]

    def test_realign_check_and_rerun(self):
        source = self.root / "lessons" / "lesson_x" / "src.py"
        source.write_text("\n".join(OLD[:3] + ["new a", "new b"] + OLD[3:]) + "\n", encoding="utf-8")
        self.assertEqual(self.run_main("--check"), 1)
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(shape(self.block()), (2, 12, [3, 10], [(7, 8)]))
        self.assertEqual(self.run_main("--check"), 0)
        before = self.content.read_bytes()
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(self.content.read_bytes(), before)

    def test_invalid_base_changes_nothing(self):
        before = self.content.read_bytes()
        self.assertEqual(self.run_main("--base", "no-such-rev"), 2)
        self.assertEqual(self.content.read_bytes(), before)

    def test_a_block_that_cannot_be_aligned_is_not_written_half_moved(self):
        # 同一份 content.json 里两块：A 块能对准、会移动，B 块的锚点被删掉。整份文件都不写入，
        # 否则 A 块的移动会和 B 块对不准的状态一起写出去。
        lesson = self.root / "lessons" / "lesson_x"
        (lesson / "other.py").write_text("\n".join(OLD) + "\n", encoding="utf-8")
        data = self.json.loads(self.content.read_text(encoding="utf-8"))
        second = {**copy.deepcopy(data["scenes"]["code"]["blocks"][0]), "id": "code-y",
                  "path": "lessons/lesson_x/other.py"}
        data["scenes"]["code"]["blocks"].append(second)
        self.content.write_text(self.json.dumps(data), encoding="utf-8")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "two blocks")
        (lesson / "src.py").write_text("\n".join(["import x", "import y"] + OLD) + "\n", encoding="utf-8")
        (lesson / "other.py").write_text("\n".join(text for text in OLD if text != "line 8") + "\n",
                                         encoding="utf-8")
        before = self.content.read_bytes()
        self.assertEqual(self.run_main(), 1)
        self.assertEqual(self.content.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
