"""Python 选择器与前端 selector.ts 语义一致：两边跑同一份共享向量。"""
import json
import unittest
from pathlib import Path

from server.selectors import MISSING, matches, resolve_path, select_events

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "frontend" / "src" / "content" / "__fixtures__" / "selector-vectors.json")
                     .read_text(encoding="utf-8"))


class SharedVectorTests(unittest.TestCase):
    def test_paths(self):
        for vector in VECTORS["paths"]:
            with self.subTest(path=vector["path"], value=vector["value"]):
                value = resolve_path(vector["value"], vector["path"])
                if vector["found"]:
                    self.assertIsNot(value, MISSING)
                    self.assertEqual(value, vector["result"])
                    self.assertIs(type(value), type(vector["result"]))
                else:
                    self.assertIs(value, MISSING)

    def test_selectors(self):
        for vector in VECTORS["selectors"]:
            with self.subTest(selector=vector["selector"]):
                self.assertEqual(select_events(vector["selector"], VECTORS["events"]), vector["matches"])

    def test_vectors_cover_every_condition(self):
        used = {key for vector in VECTORS["selectors"] for key, value in vector["selector"].items()
                if value is not None}
        self.assertEqual(used, {"event", "round", "path", "span_kind", "name"})


class PythonSpecificTests(unittest.TestCase):
    def test_bool_is_not_a_number_and_null_is_present(self):
        event = {"type": "x", "round": True, "data": {"value": None}}
        self.assertFalse(matches({"round": 1}, event))
        self.assertTrue(matches({"path": "data.value"}, event))
        self.assertFalse(matches({"path": "data.value.inner"}, event))


if __name__ == "__main__":
    unittest.main()
