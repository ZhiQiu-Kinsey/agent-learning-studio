"""scripts/realign_notes.py：源码插删行后，批注、块起止和折叠区间只按实际位置移动。"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from realign_notes import LineMap, mapping_for, realign_block  # noqa: E402

OLD = [f"line {number}" for number in range(1, 13)]
BLOCK = {"id": "code-x", "start": 2, "end": 10,
         "notes": [{"id": "n3", "line": 3, "anchor": "line 3"}, {"id": "n8", "line": 8, "anchor": "line 8"}],
         "folds": [{"id": "fold", "start": 5, "end": 6, "label": "平台代码"}]}


def realign(new, mapping=True):
    block = copy.deepcopy(BLOCK)
    realign_block(block, new, LineMap(OLD, new) if mapping else None)
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
        realign_block(first, new, mapping_for(first, BLOCK, OLD, new))
        self.assertEqual(shape(first), (2, 12, [3, 10], [(7, 8)]))
        # 第二次：块已经不是 --base 那一版的行号，不再套映射；锚点都对，什么也不动。
        second = copy.deepcopy(first)
        self.assertIsNone(mapping_for(second, BLOCK, OLD, new))
        self.assertEqual(realign_block(second, new, None), [])
        self.assertEqual(shape(second), shape(first))

    def test_no_mapping_when_the_source_did_not_change(self):
        self.assertIsNone(mapping_for(copy.deepcopy(BLOCK), BLOCK, OLD, list(OLD)))
        self.assertIsNone(mapping_for(copy.deepcopy(BLOCK), BLOCK, None, OLD))

    def test_missing_or_ambiguous_anchor_is_an_error(self):
        new = [text for text in OLD if text != "line 8"]
        with self.assertRaisesRegex(ValueError, "找不到唯一的锚点"):
            realign(new)


if __name__ == "__main__":
    unittest.main()
