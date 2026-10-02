"""Skills 与渐进式披露的行为测试：确定性模型数据，技能文件与 load_skill 在 Python 中真实读取和执行。"""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_skills_disclosure import runtime
from lessons.lesson_skills_disclosure.fixtures import create_completion


def run_case(exercise_id, inputs, completion=None, budget=4, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="skills-disclosure", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def with_usage(completion, per_char=4):
    """在确定性响应上补一个按请求长度计算的 prompt_tokens，只为测试报告的取值与合计。"""
    def complete(body, key):
        response = completion(body, key)
        size = len(json.dumps(body["messages"], ensure_ascii=False))
        return {**response, "usage": {"prompt_tokens": size // per_char, "completion_tokens": 10}}
    return complete


def reply(content=None, calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def load_call(name, call_id="call_1"):
    return {"id": call_id, "type": "function",
            "function": {"name": "load_skill", "arguments": json.dumps({"name": name})}}


class SkillFileTests(unittest.TestCase):
    def test_every_registered_skill_has_frontmatter_and_body(self):
        for name in runtime.SKILL_NAMES:
            with self.subTest(name=name):
                skill = runtime.read_skill(name)
                self.assertEqual(skill["name"], name)
                self.assertGreater(len(skill["description"]), 20)
                self.assertNotIn("---", skill["body"][:5])
                self.assertIn("## 做法", skill["body"])

    def test_catalog_lists_only_name_and_description(self):
        skills = runtime.skill_list("precise")
        catalog, full = runtime.catalog_prompt(skills), runtime.full_prompt(skills)
        for skill in skills:
            self.assertIn(f"- {skill['name']}：{skill['description']}", catalog)
            self.assertNotIn(skill["body"], catalog)
            self.assertIn(skill["body"], full)
        self.assertLess(len(catalog) * 3, len(full))

    def test_vague_variant_changes_only_one_description(self):
        precise, vague = runtime.skill_list("precise"), runtime.skill_list("vague")
        self.assertEqual(vague[0]["description"], runtime.VAGUE_DESCRIPTION)
        self.assertEqual(vague[0]["body"], precise[0]["body"])
        self.assertEqual(vague[1:], precise[1:])

    def test_load_skill_reads_only_registered_names(self):
        self.assertEqual(runtime.load_skill("review-cards")["instructions"], runtime.read_skill("review-cards")["body"])
        for name in ("../../local_config", "review-cards/../error-question", "Review-Cards", ""):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "没有名为"):
                runtime.load_skill(name)


class CompareTests(unittest.TestCase):
    def test_both_modes_record_tokens_skills_and_a_comparison_table(self):
        answer, events = run_case("compare-cards", {"mode": "both"},
                                  with_usage(create_completion("compare-cards", {})))
        requests = [data["body"] for data in of(events, "request")]
        self.assertEqual(len(requests), 3)
        self.assertNotIn("tools", requests[0])
        self.assertEqual(requests[1]["tools"][0]["function"]["name"], "load_skill")
        records = of(events, "lesson.skill_request")
        self.assertEqual([(r["mode"], r["round"]) for r in records], [("full", 1), ("on_demand", 2), ("on_demand", 3)])
        self.assertEqual(records[0]["skills_in_context"], list(runtime.SKILL_NAMES))
        self.assertEqual(records[1]["skills_in_context"], [])
        self.assertEqual(records[1]["proposed_loads"], ["review-cards"])
        self.assertEqual(records[2]["skills_in_context"], ["review-cards"])
        self.assertLess(records[1]["prompt_tokens"], records[0]["prompt_tokens"])
        result = of(events, "tool_result")[0]
        self.assertEqual(result["result"]["result"]["instructions"], runtime.read_skill("review-cards")["body"])
        report = of(events, "lesson.report")[-1]
        full_row, demand_row = report["table"]["rows"]
        self.assertEqual(full_row[:2], ["全量注入", 1])
        self.assertEqual(full_row[3], records[0]["prompt_tokens"])
        self.assertEqual(demand_row[2], f"{records[1]['prompt_tokens']} → {records[2]['prompt_tokens']}")
        self.assertEqual(demand_row[3], records[1]["prompt_tokens"] + records[2]["prompt_tokens"])
        self.assertEqual(demand_row[4], "第 2 次请求提出 review-cards")
        self.assertEqual(demand_row[5], "正确：加载了 review-cards")
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        self.assertIn("【全量注入】", answer)
        self.assertIn("【目录 + 按需加载】", answer)

    def test_missing_usage_is_reported_not_zero(self):
        _, events = run_case("compare-chat", {"mode": "both", "task": "chat"})
        records = of(events, "lesson.skill_request")
        self.assertTrue(all(record["prompt_tokens"] is None for record in records))
        rows = of(events, "lesson.report")[-1]["table"]["rows"]
        self.assertEqual([row[2:4] for row in rows], [["未报告", "未报告"], ["未报告", "未报告"]])
        self.assertEqual(rows[1][5], "正确：没有加载")
        self.assertEqual(of(events, "tool_call"), [])

    def test_partial_usage_is_marked(self):
        calls = []

        def provider(body, key):
            calls.append(body)
            response = create_completion("cards-precise", {})(body, key)
            return {**response, "usage": {"prompt_tokens": 120}} if len(calls) == 1 else response
        _, events = run_case("cards-precise", {"mode": "on_demand"}, provider)
        row = of(events, "lesson.report")[-1]["table"]["rows"][0]
        self.assertEqual(row[2:4], ["120 → 未报告", "120（1 次未报告）"])


class TriggerTests(unittest.TestCase):
    def test_vague_description_records_a_missed_and_a_false_trigger(self):
        _, events = run_case("cards-vague", {"mode": "on_demand", "description": "vague"})
        self.assertIn("review-cards：帮助学习。", of(events, "request")[0]["body"]["messages"][0]["content"])
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["table"]["rows"][0][5], "漏触发：该加载却没加载")
        # 回答格式照样通过：只看回答，看不出技能没被加载。
        self.assertTrue(next(c for c in report["checks"] if c["label"].endswith("回答格式初筛"))["passed"])
        _, events = run_case("question-vague", {"mode": "on_demand", "task": "review_question", "description": "vague"})
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["table"]["rows"][0][5], "误触发：加载了 review-cards")
        self.assertFalse(next(c for c in report["checks"] if c["label"] == "按需加载：加载判定")["passed"])

    def test_precise_description_skips_loading_for_a_plain_question(self):
        _, events = run_case("question-precise", {"mode": "on_demand", "task": "review_question"})
        self.assertEqual(len(of(events, "request")), 1)
        self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"][0][5], "正确：没有加载")

    def test_unknown_skill_name_becomes_a_structured_error(self):
        def provider(body, key):
            if not any(message["role"] == "tool" for message in body["messages"]):
                return reply(calls=[load_call("../../local_config")])
            return reply("没有找到合适的技能，直接回答。")
        _, events = run_case("cards-precise", {"mode": "on_demand"}, provider)
        result = of(events, "tool_result")[0]["result"]
        self.assertEqual((result["ok"], result["error_type"]), (False, "ValueError"))
        self.assertIn("技能目录里只有", result["error"])
        follow_up = of(events, "request")[1]["body"]["messages"]
        self.assertEqual(follow_up[-1]["role"], "tool")
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["table"]["rows"][0][5], "漏触发：该加载却没加载")
        self.assertIn("未登记的技能名被拒绝", [check["label"] for check in report["checks"]])

    def test_wrong_skill_is_called_wrong(self):
        def provider(body, key):
            if not any(message["role"] == "tool" for message in body["messages"]):
                return reply(calls=[load_call("three-sentence-summary")])
            return reply("1. 列表可变。\n2. 元组不可变。\n3. 集合去重。")
        _, events = run_case("cards-precise", {"mode": "on_demand"}, provider)
        row = of(events, "lesson.report")[-1]["table"]["rows"][0]
        self.assertEqual(row[5], "加载错技能：three-sentence-summary")
        self.assertTrue(row[6].startswith("未通过："))


class LimitTests(unittest.TestCase):
    def test_round_limit_stops_without_an_answer(self):
        def provider(body, key):
            return reply(calls=[load_call("review-cards", f"call_{len(body['messages'])}")])
        answer, events = run_case("cards-precise", {"mode": "on_demand"}, provider)
        self.assertEqual(len(of(events, "request")), runtime.ON_DEMAND_LIMIT)
        self.assertIn("次请求内没有得到回答", answer)
        self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"][0][6], "未通过：没有回答")

    def test_cancel_and_inputs(self):
        with self.assertRaises(RunCancelled):
            run_case("compare-cards", {}, cancelled=lambda: True)
        for bad in ({"mode": "all"}, {"task": "poem"}, {"description": "short"}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_format_screen_counts_cards_with_markdown(self):
        text = "**问：** 列表能改吗？\n**答：** 能。\n\n1. 问：元组呢？\n答：不能。\n\n- 问：集合？\n- 答：去重。"
        self.assertEqual(runtime.count_cards(text), (3, 3))
        self.assertEqual(runtime.format_screen("review-cards", text)[0], True)
        self.assertEqual(runtime.format_screen(None, text), (False, "写成了 3 张复习卡"))


if __name__ == "__main__":
    unittest.main()
