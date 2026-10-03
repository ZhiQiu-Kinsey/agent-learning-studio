"""选择器的 Python 实现与共享测试向量：与 frontend/src/content/selector.ts 保持同一语义。"""
import json
import unittest
from pathlib import Path

from server.content_schema import Selector
from server.selectors import MISSING, count_events, find_evidence, resolve_path, select_events, selector_matches

VECTORS = json.loads((Path(__file__).parent / "fixtures" / "selector_vectors.json").read_text(encoding="utf-8"))


class SharedVectorTests(unittest.TestCase):
    def test_resolve_path(self):
        for case in VECTORS["resolve_path"]:
            with self.subTest(path=case["path"]):
                value = resolve_path(case["value"], case["path"])
                if case["found"]:
                    self.assertIsNot(value, MISSING)
                    self.assertEqual(value, case["result"])
                    self.assertIs(type(value), type(case["result"]))
                else:
                    self.assertIs(value, MISSING)

    def test_select_events(self):
        events = VECTORS["events"]
        for case in VECTORS["select"]:
            with self.subTest(selector=case["selector"]):
                self.assertEqual(select_events(case["selector"], events), case["indices"])

    def test_find_evidence(self):
        events = VECTORS["events"]
        for case in VECTORS["evidence"]:
            with self.subTest(selector=case["selector"], start=case["from"]):
                result = find_evidence(case["selector"], events, case["from"])
                if not case["found"]:
                    self.assertEqual(result, {"found": False})
                    continue
                self.assertEqual((result["found"], result["index"]), (True, case["index"]))
                expected = events[case["index"]] if case.get("value_is_event") else case["value"]
                self.assertEqual(result["value"], expected)

    def test_count_events(self):
        for case in VECTORS["count_events"]:
            with self.subTest(rule=case["rule"]):
                self.assertEqual(count_events(case["rule"], VECTORS["events"]), case["count"])


class SelectorModelTests(unittest.TestCase):
    def test_accepts_the_content_schema_model(self):
        events = VECTORS["events"]
        selector = Selector(event="tool_call", name="add_numbers")
        self.assertEqual(select_events(selector, events), [3])

    def test_rejects_unknown_conditions(self):
        with self.assertRaises(ValueError):
            selector_matches({"event": "request", "kind": "llm"}, VECTORS["events"][1])

    def test_booleans_are_not_numbers(self):
        # JS 的 === 不把 true 当作 1：轮次条件不能被布尔值误配。
        self.assertFalse(selector_matches({"round": 1}, {"type": "x", "round": True, "data": {}}))
        self.assertTrue(selector_matches({"round": 1}, {"type": "x", "round": 1.0, "data": {}}))

    def test_nth_picks_among_hits_and_is_not_a_condition(self):
        events = VECTORS["events"]
        self.assertEqual(select_events(Selector(event="tool_call", nth=2), events), [5])
        # 单条事件不知道自己排第几：第一个 tool_call 仍满足全部条件。
        self.assertTrue(selector_matches({"event": "tool_call", "nth": 2}, events[3]))
        with self.assertRaises(ValueError):
            Selector(nth=2)  # 只有 nth 等于“整次运行的第 2 条事件”，不是在找证据
        for bad in (0, -1, True, 1.5):
            with self.subTest(nth=bad), self.assertRaises(ValueError):
                select_events({"event": "tool_call", "nth": bad}, events)


if __name__ == "__main__":
    unittest.main()
