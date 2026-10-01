"""教学示意契约：结构与真实运行一致，又不能冒充运行记录。"""
import copy
import unittest

from pydantic import ValidationError

from server.content_schema import LessonContent
from server.illustrations import IllustrationError, validate_illustration

VALID = [
    {"type": "request", "round": 1, "data": {"body": {"messages": [{"role": "user", "content": "19 加 23"}]}}},
    {"type": "response", "round": 1, "data": {"body": {"tool_calls": [{"id": "call_example"}]}}},
    {"type": "tool_call", "round": 1, "data": {"id": "call_example", "function": {"name": "add_numbers"}}},
    {"type": "tool_result", "round": 1, "data": {"tool_call_id": "call_example", "result": {"ok": True}}},
    {"type": "request", "round": 2, "data": {}},
    {"type": "response", "round": 2, "data": {}},
    {"type": "answer", "round": 2, "data": {"content": "示意回答"}},
    {"type": "lesson.state", "round": 2, "data": {"step": "done"}},
]


def mutated(index, **changes):
    events = copy.deepcopy(VALID)
    if changes.pop("_delete", False):
        del events[index]
    else:
        events[index].update(changes)
    return events


class IllustrationContractTests(unittest.TestCase):
    def test_valid_sequence_passes(self):
        validate_illustration(copy.deepcopy(VALID))

    def test_violations_are_rejected(self):
        cases = {
            "unknown type": mutated(0, type="thinking"),
            "run envelope": [{"type": "run_start", "data": {}}] + copy.deepcopy(VALID),
            "real looking id": mutated(2, data={"id": "call_8f2a91", "function": {}}),
            "result without call": mutated(3, data={"tool_call_id": "call_example_2"}),
            "call without result": mutated(3, _delete=True),
            "response without request": mutated(0, _delete=True),
            "round goes back": mutated(4, round=0),
            "tool after answer": copy.deepcopy(VALID) + [
                {"type": "tool_call", "round": 2, "data": {"id": "call_example_late"}}],
            "timing field": mutated(1, data={"duration_ms": 812}),
            "usage field": mutated(1, data={"body": {"usage": {"total_tokens": 31}}}),
            "measured text": mutated(3, data={"tool_call_id": "call_example", "result": "12 passed in 0.42s"}),
            "chinese timing": mutated(6, data={"content": "耗时 3 秒"}),
        }
        for name, events in cases.items():
            with self.subTest(name):
                with self.assertRaises(IllustrationError):
                    validate_illustration(events)

    def test_content_schema_enforces_the_contract(self):
        content = {
            "schema_version": 2, "lesson": "tool-selection", "source_language": "zh-CN",
            "scenes": {"understand": {"blocks": [
                {"type": "flow", "id": "loop", "illustration": "loop"}]}},
            "illustrations": {"loop": {"events": copy.deepcopy(VALID)}},
        }
        self.assertEqual(LessonContent.model_validate(content).illustrations["loop"].provenance, "illustration")
        content["illustrations"]["loop"]["events"] = mutated(2, data={"id": "call_real"})
        with self.assertRaisesRegex(ValidationError, "示例 id"):
            LessonContent.model_validate(content)


if __name__ == "__main__":
    unittest.main()
