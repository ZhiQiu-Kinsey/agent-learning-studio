"""读码批注密度门槛：新块必须达标；基线里已经达标的块要从基线删除（基线只许减少）。"""
import unittest

from scripts.validate_lessons import DENSITY_BASELINE, ROOT, validate, validate_note_density
from server.code_reading import MAX_GAP, NOTE_EVERY, note_density
from server.content_schema import AnnotatedSource


class NoteDensityTests(unittest.TestCase):
    def test_all_lessons_meet_the_gate_or_are_in_the_shrinking_baseline(self):
        new, fixed = validate_note_density(ROOT, validate(ROOT))
        self.assertEqual(new, [], "新的读码块批注不足，规则见 docs/architecture/curriculum-plan-2026-10.md 8.4")
        self.assertEqual(fixed, [], f"这些块已达标，请从 {'/'.join(DENSITY_BASELINE)} 删除")

    def test_folded_and_blank_lines_do_not_count(self):
        lines = ["a = 1", "", "b = 2", "c = 3", "d = 4"]
        block = AnnotatedSource.model_validate({
            "id": "b", "type": "annotated-source", "path": "x.py", "start": 1, "end": 5,
            "notes": [{"id": "n", "line": 1, "anchor": "a", "text": "说明"}],
            "folds": [{"id": "f", "start": 3, "end": 4, "label": "平台"}]})
        self.assertEqual(note_density(block, lines), {"lines": 2, "notes": 1, "longest_gap": 1})

    def test_thresholds_match_the_documented_rule(self):
        self.assertEqual((NOTE_EVERY, MAX_GAP), (8, 12))


if __name__ == "__main__":
    unittest.main()
