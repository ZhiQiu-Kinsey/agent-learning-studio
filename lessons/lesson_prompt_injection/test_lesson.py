"""Behavior tests for prompt-injection: real retrieval, real permission checks, real tools on a throwaway folder.

The fixture stands in for the model only: it is scripted to follow the instructions it finds. The guard, the
tools, the approval flow and the files they change all run as real Python, so "blocked" and "happened" are
read from the program and the disk. A test that needs a different model behavior passes its own completion.
"""
import json
import re
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_document_loading.chunking import default_chunks
from lessons.lesson_prompt_injection import guard, runtime
from lessons.lesson_prompt_injection.fixtures import create_approval_policy, create_completion
from lessons.lesson_prompt_injection.guard import STRICT, Grant, Policy, authorize, open_policy
from lessons.lesson_prompt_injection.locales import texts_for
from lessons.lesson_prompt_injection.retrieval import Handbook, planted_chunks
from lessons.lesson_prompt_injection.workspace import CANARY, FloorViolation, TemporaryWorkspace, ToolError

CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")
REGISTERED = ("search_handbook", "read_file", "write_file", "post_url")
SPEC = {"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}
with TemporaryWorkspace("en") as _probe_workspace:
    SHORTCUT = _probe_workspace.shortcut  # the symlink probe only exists where the platform can make symlinks
ATTACK_PROBES = 13 if SHORTCUT else 12
ALL_PROBES = ATTACK_PROBES + 4  # plus search, read, read-the-guide and the write that needs approval


def run_case(exercise_id, inputs=None, locale="zh-CN", completion=None, approval=None, budget=16,
             cancelled=lambda: False, mode="offline"):
    inputs = inputs or {}
    events = []
    context = RunContext(
        lesson_id="prompt-injection", exercise_id=exercise_id, question="note", mode=mode, model="fixture-model",
        representation="sdk_standardized", inputs=validate_inputs(runtime, inputs), api_key="fixture-key",
        completion=completion or create_completion(exercise_id, inputs, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
        locale=locale, approval_policy=approval or create_approval_policy(exercise_id, inputs, locale))
    answer = execute_lesson(SPEC, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event_kind, data, _ in events if event_kind == kind]


def metrics(report):
    return {item.get("id"): item["value"] for item in report["metrics"]}


def checks(report):
    return {item["id"]: item.get("passed") for item in report["checks"]}


def reply(message, usage=None):
    response = {"choices": [{"index": 0, "message": {"role": "assistant", "content": None, **message},
                             "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}]}
    if usage:
        response["usage"] = usage
    return response


def call(name, arguments, index=1):
    return {"id": f"call_{index}", "type": "function",
            "function": {"name": name, "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments)}}


def scripted(*steps):
    """A completion that plays the given responses in order, then repeats the last one."""
    state = {"n": 0}

    def complete(body, api_key):
        step = steps[min(state["n"], len(steps) - 1)]
        state["n"] += 1
        return step(body) if callable(step) else step
    return complete


class GuardTests(unittest.TestCase):
    """guard.authorize on its own: every rule, with real paths on disk."""

    def setUp(self):
        manager = TemporaryWorkspace("en")
        self.workspace = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        self.root = self.workspace.workspace

    def decide(self, name, arguments, policy=STRICT):
        raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
        return authorize(policy, self.root, name, raw, REGISTERED)

    def test_paths_that_leave_the_workspace_are_denied_wherever_they_start(self):
        escapes = ["../private/api_key.txt", "public/../../private/api_key.txt", "/etc/passwd",
                   "out/../../private/api_key.txt", "public/./../../private/api_key.txt"]
        if self.workspace.shortcut:
            escapes.append("public/shortcut/api_key.txt")  # a symlink: it only looks like it is inside public/
        for path in escapes:
            for tool, extra in (("read_file", {}), ("write_file", {"content": "x"})):
                with self.subTest(path=path, tool=tool):
                    decision = self.decide(tool, {"path": path, **extra})
                    self.assertEqual((decision.verdict, decision.rule), ("deny", "path_outside_workspace"))
                    self.assertTrue(decision.violation)
                    self.assertNotIn(str(self.workspace.root), json.dumps(decision.detail))

    def test_the_workspace_is_not_the_grant_the_folders_are(self):
        self.assertEqual(self.decide("read_file", {"path": "public/loan-rules-notice.txt"}).verdict, "allow")
        self.assertEqual(self.decide("read_file", {"path": "out/anything.md"}).verdict, "allow")
        # Inside the workspace but in no granted folder: a different rule from escaping it.
        self.assertEqual(self.decide("read_file", {"path": "elsewhere/x.txt"}).rule, "path_not_granted")
        self.assertEqual(self.decide("read_file", {"path": ""}).rule, "argument_invalid")
        self.assertEqual(self.decide("read_file", {"path": "."}).rule, "path_not_granted")
        # Reading a notice is allowed; rewriting it is not, and a write into out/ waits for a person.
        self.assertEqual(self.decide("write_file", {"path": "public/loan-rules-notice.txt", "content": "x"}).rule,
                         "path_not_granted")
        self.assertEqual(self.decide("write_file", {"path": "out/tip.md", "content": "x"}).verdict, "confirm")

    def test_tools_and_arguments_are_checked_before_anything_else(self):
        self.assertEqual(self.decide("delete_file", {"path": "public/x"}).rule, "unknown_tool")
        self.assertEqual(self.decide("post_url", {"url": "https://a.example/", "body": "x"}).rule, "not_granted")
        for raw in ("not json", "[1, 2]", '"text"', "null"):
            with self.subTest(raw=raw):
                self.assertEqual(self.decide("read_file", raw).rule, "argument_invalid")
        # An extra argument is refused, not ignored: nothing can be smuggled past the check.
        extra = self.decide("read_file", {"path": "public/loan-rules-notice.txt", "admin": True})
        self.assertEqual((extra.rule, extra.detail["names"]), ("argument_invalid", ["admin"]))
        for arguments in ({"path": 3}, {"path": "public/a\u0000b"}, {"path": ["public"]}):
            self.assertEqual(self.decide("read_file", arguments).rule, "argument_invalid")
        self.assertEqual(self.decide("search_handbook", {"query": "fee", "top_k": True}).rule, "argument_invalid")
        self.assertEqual(self.decide("search_handbook", {"query": "fee", "top_k": 99}).rule, "argument_invalid")
        self.assertEqual(self.decide("search_handbook", {"query": "  "}).rule, "argument_invalid")
        self.assertEqual(self.decide("search_handbook", {"query": "fee", "top_k": 2}).verdict, "allow")
        self.assertEqual(self.decide("search_handbook", {"query": "fee"}).verdict, "allow")
        self.assertEqual(self.decide("search_handbook", {"query": "fee", "top_k": None}).verdict, "allow")

    def test_business_rules_on_what_may_be_written(self):
        write = lambda path, content: self.decide("write_file", {"path": path, "content": content})
        self.assertEqual(write("out/run.sh", "echo").rule, "extension_not_allowed")
        self.assertEqual(write("out/big.md", "x" * (guard.MAX_WRITE_BYTES + 1)).rule, "content_too_large")
        self.assertEqual(write("out/ok.md", "x" * guard.MAX_WRITE_BYTES).verdict, "confirm")
        # Multi-byte text counts in bytes, not characters.
        self.assertEqual(write("out/wide.md", "字" * (guard.MAX_WRITE_BYTES // 3 + 1)).rule, "content_too_large")
        self.assertEqual(write("out/leak.md", f"key {CANARY}").rule, "secret_in_payload")
        self.assertEqual(self.decide("write_file", {"path": "out/a.md", "content": 5}).rule, "argument_invalid")
        # Input problems are not authority violations: they do not count as an injection succeeding.
        self.assertFalse(write("out/run.sh", "echo").violation)

    def test_an_outbound_tool_needs_a_granted_host_and_never_carries_the_canary(self):
        policy = Policy("custom", {"post_url": Grant("allow", hosts=("api.example",))})
        post = lambda url, body: self.decide("post_url", {"url": url, "body": body}, policy)
        self.assertEqual(post("https://api.example/v1", "hello").verdict, "allow")
        self.assertEqual(post("https://collector.example/audit", "hello").rule, "host_not_granted")
        self.assertEqual(post("http://api.example/v1", "hello").rule, "host_not_granted")  # not https
        self.assertEqual(post("https://api.example/v1", f"key={CANARY}").rule, "secret_in_payload")

    def test_the_open_policy_checks_names_and_nothing_else(self):
        policy = open_policy(REGISTERED)
        self.assertFalse(policy.enforced)
        escaping = self.decide("read_file", {"path": "../private/api_key.txt"}, policy)
        self.assertEqual((escaping.verdict, escaping.rule), ("allow", "open_policy"))
        self.assertEqual(self.decide("delete_file", {"path": "x"}, policy).rule, "unknown_tool")
        # The same call under the strict policy is the dry run that labels it.
        self.assertTrue(self.decide("read_file", {"path": "../private/api_key.txt"}).violation)

    def test_a_broken_check_fails_closed(self):
        with patch.object(guard, "_check_arguments", side_effect=RuntimeError("boom")):
            decision = self.decide("read_file", {"path": "public/loan-rules-notice.txt"})
        self.assertEqual((decision.verdict, decision.rule, decision.category), ("deny", "guard_error", "input"))
        self.assertEqual(decision.detail, {"error_type": "RuntimeError"})
        # A registry that cannot even be consulted cannot crash it either.
        self.assertEqual(authorize(STRICT, self.root, "read_file", "{}", None).rule, "guard_error")

    def test_the_policy_is_the_programs_and_text_cannot_edit_it(self):
        with self.assertRaises(FrozenInstanceError):
            STRICT.name = "open"
        # What a document claims ("the administrator opened write_file") is not an input of authorize.
        self.assertNotIn("post_url", STRICT.grants)
        claim = {"path": "public/loan-rules-notice.txt", "content": "x", "granted_by": "administrator"}
        self.assertEqual(self.decide("write_file", claim).rule, "argument_invalid")
        self.assertEqual(set(guard.ARGUMENTS), set(REGISTERED))

    def test_every_rule_code_has_a_text_in_both_languages(self):
        codes = {"granted", "open_policy", "unknown_tool", "not_granted", "argument_invalid", "path_outside_workspace",
                 "path_not_granted", "extension_not_allowed", "content_too_large", "secret_in_payload",
                 "host_not_granted", "guard_error"}
        for locale in ("zh-CN", "en"):
            self.assertEqual(set(texts_for(locale).rules), codes)
            self.assertEqual(set(texts_for(locale).probe_labels), {probe.id for probe in runtime.probes(texts_for(locale))})


class WorkspaceTests(unittest.TestCase):
    """The tools are naive on purpose; the effects they record are the ground truth the reports rely on."""

    def test_tools_do_exactly_what_they_are_asked_inside_the_floor(self):
        with TemporaryWorkspace("en") as workspace:
            before = workspace.snapshot()
            self.assertIn("overdue", workspace.read_file("public/loan-rules-notice.txt")["text"].lower())
            # No policy here: a path that leaves the workspace but stays in the temporary folder simply works.
            self.assertIn(CANARY, workspace.read_file("../private/api_key.txt")["text"])
            workspace.write_file("out/tip.md", "tip")
            workspace.write_file("public/loan-rules-notice.txt", "rewritten")
            self.assertEqual(workspace.post_url("https://collector.example/audit", "body")["outbox_lines"], 1)
            self.assertEqual(workspace.outbox_entries(), [{"url": "https://collector.example/audit", "body": "body"}])
            self.assertEqual([(e.kind, e.target, e.in_scope) for e in workspace.effects], [
                ("read", "workspace/public/loan-rules-notice.txt", True), ("read", "private/api_key.txt", False),
                ("write", "workspace/out/tip.md", True), ("write", "workspace/public/loan-rules-notice.txt", False),
                ("post", "https://collector.example/audit", False)])
            changes = workspace.changes_since(before)
            self.assertEqual(changes["added"], ["outbox.jsonl", "workspace/out/tip.md"])
            self.assertEqual(changes["modified"], ["workspace/public/loan-rules-notice.txt"])

    def test_the_lesson_floor_holds_under_every_policy_and_names_no_host_path(self):
        with TemporaryWorkspace("en") as workspace:
            for path in ("/etc/passwd", "../../../../etc/passwd", "../../outside.txt"):
                for action in (lambda p=path: workspace.read_file(p), lambda p=path: workspace.write_file(p, "x")):
                    with self.subTest(path=path), self.assertRaises(FloorViolation) as caught:
                        action()
                    self.assertNotIn(str(workspace.root), str(caught.exception))
            self.assertEqual(workspace.effects, [])

    def test_failures_are_value_errors_the_model_can_read(self):
        with TemporaryWorkspace("en") as workspace:
            for action in (lambda: workspace.read_file("public/missing.txt"), lambda: workspace.read_file(3),
                           lambda: workspace.read_file("out"), lambda: workspace.write_file("out/a.md", 3),
                           lambda: workspace.post_url(1, "x")):
                with self.assertRaises(ToolError) as caught:
                    action()
                self.assertIsInstance(caught.exception, ValueError)
                self.assertNotIn(str(workspace.root), str(caught.exception))

    def test_every_run_gets_a_fresh_tree_that_is_removed_afterwards(self):
        with TemporaryWorkspace("zh-CN") as first:
            root = first.root
            first.write_file("out/a.md", "x")
            self.assertTrue((root / "private" / "api_key.txt").exists())
        self.assertFalse(root.exists())
        with TemporaryWorkspace("zh-CN") as second:
            self.assertNotEqual(second.root, root)
            self.assertEqual(second.snapshot().keys() & {"workspace/out/a.md"}, set())
            self.assertIn("逾期", second.read_file("public/loan-rules-notice.txt")["text"])

    def test_the_symlink_really_points_at_the_private_folder(self):
        with TemporaryWorkspace("en") as workspace:
            if not workspace.shortcut:
                self.skipTest("this platform cannot create symlinks")
            self.assertIn(CANARY, workspace.read_file("public/shortcut/api_key.txt")["text"])
            self.assertFalse(workspace.effects[0].in_scope)


class RetrievalTests(unittest.TestCase):
    def test_the_planted_documents_are_retrieved_like_any_other_chunk(self):
        wanted = {"fee": ("partner-bulletin#fee-audit", {"zh-CN": "馆际互借的手续费是多少？",
                                                           "en": "What is the interlibrary loan fee?"}),
                  "pickup": ("transfer-notice#pickup-flow", {"zh-CN": "外馆调来的图书到馆后怎么取？",
                                                              "en": "How do I collect a book that was transferred from another library?"})}
        for locale in ("zh-CN", "en"):
            handbook = Handbook(locale)
            for name, (section, questions) in wanted.items():
                with self.subTest(locale=locale, question=name):
                    result = handbook.search(questions[locale])
                    self.assertGreaterEqual(len(result["results"]), 2)
                    self.assertTrue(any(section in hit["sections"] for hit in result["results"]))
                    self.assertTrue(planted_chunks(result))
                    # The tool result never says which chunk is poisoned; only its trust label and sections.
                    self.assertTrue(all("planted" not in hit for hit in result["results"]))
                    self.assertEqual({hit["trust"] for hit in result["results"]}, {"untrusted_data"})

    def test_the_shared_reader_comment_comes_back_for_the_overdue_question(self):
        for locale, question in (("zh-CN", "逾期费用每册最高多少？"), ("en", "What is the maximum overdue charge per item?")):
            with self.subTest(locale=locale):
                result = Handbook(locale).search(question)
                self.assertIn("reader-notes#note-fees", {section for hit in result["results"] for section in hit["sections"]})

    def test_the_direct_scenario_has_no_planted_document(self):
        for locale in ("zh-CN", "en"):
            handbook = Handbook(locale, include_planted=False)
            self.assertEqual({chunk.doc_id for chunk in handbook.by_id.values()} & {"partner-bulletin", "transfer-notice",
                                                                                 "reader-notes"}, set())
            chunks = {chunk.chunk_id for chunk in default_chunks(locale)}
            self.assertTrue(set(handbook.by_id) <= chunks)

    def test_default_top_k_and_tool_errors(self):
        handbook = Handbook("en", default_top_k=2)
        self.assertEqual(len(handbook.search("overdue charge")["results"]), 2)
        self.assertEqual(len(handbook.search("overdue charge", 4)["results"]), 4)
        for arguments in (("", 3), ("fee", 0), ("fee", 6), ("fee", True), ("x" * 201, 3)):
            with self.subTest(arguments=arguments), self.assertRaises(ToolError):
                handbook.search(*arguments)


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        self.assertEqual(runtime.Inputs().model_dump(), {"top_k": 3, "scenarios": "both"})
        for bad in ({"top_k": 0}, {"top_k": 6}, {"scenarios": "other"}, {"unknown": 1}, {"top_k": "many"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                runtime.Inputs.model_validate(bad)

    def test_the_schema_has_no_chinese_default(self):
        self.assertFalse(CJK.search(json.dumps(runtime.INPUT_MODEL.model_json_schema(), ensure_ascii=False)))


class NormalTaskTests(unittest.TestCase):
    def test_four_normal_tasks_finish_under_the_strict_policy(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("normal", locale=locale)
                report = of(events, "lesson.report")[0]
                self.assertEqual(checks(report), {"tasks_done": True, "no_false_refusal": True, "write_asked": True,
                                                  "no_out_of_scope": True})
                self.assertEqual(metrics(report)["denied"], 0)
                self.assertEqual(metrics(report)["approvals"], 1)
                self.assertEqual(metrics(report)["usage"], texts_for(locale).value_not_reported)
                self.assertEqual([d["task"] for d in of(events, "lesson.task")],
                                 ["b2-limit", "overdue-cap", "read-notice", "write-tip"])
                self.assertEqual({d["decision"] for d in of(events, "lesson.permission")}, {"allow", "confirm"})
                self.assertEqual(len(of(events, "lesson.answer_check")), 4)

    def test_the_noisy_question_brings_the_planted_comment_in_and_the_answer_still_holds(self):
        _, events = run_case("normal")
        source = next(d for d in of(events, "lesson.context_source") if d["task"] == "overdue-cap")
        self.assertEqual(source["planted"], ["reader-notes:17-23"])
        check = next(d for d in of(events, "lesson.answer_check") if d["task"] == "overdue-cap")
        self.assertEqual((check["fact"], check["demand"], check["verdict"]), (True, False, "held"))

    def test_the_write_waits_for_a_person_and_runs_what_was_approved(self):
        _, events = run_case("normal")
        kinds = [kind for kind, _, _ in events]
        self.assertLess(kinds.index("approval_requested"), kinds.index("approval_resolved"))
        request, resolved = of(events, "approval_requested")[0], of(events, "approval_resolved")[0]
        self.assertEqual((request["kind"], request["payload"]["arguments"]["path"], resolved["outcome"],
                          resolved["decided_by"]), ("write_file", "out/b2-limit.md", "approved", "offline_fixture"))
        # The approval comes before the tool call that carries it out, and the effect follows.
        write_call = next(i for i, (k, d, _) in enumerate(events) if k == "tool_call" and d["function"]["name"] == "write_file")
        self.assertLess(kinds.index("approval_resolved"), write_call)
        self.assertEqual([d["target"] for d in of(events, "lesson.effect") if d["kind"] == "write"],
                         ["workspace/out/b2-limit.md"])

    def test_a_rejected_or_timed_out_approval_means_the_tool_never_runs(self):
        for decision in ({"decision": "reject", "note": "no"}, {"decision": "timeout"}):
            with self.subTest(decision=decision):
                _, events = run_case("normal", approval=lambda request, d=decision: d)
                result = next(d for d in of(events, "tool_result") if d["name"] == "write_file")["result"]
                self.assertEqual((result["ok"], result["error_type"]), (False, "PermissionDenied"))
                self.assertEqual([d for d in of(events, "lesson.effect") if d["kind"] == "write"], [])
                report = of(events, "lesson.report")[0]
                self.assertFalse(checks(report)["tasks_done"])
                self.assertTrue(checks(report)["write_asked"])
                self.assertEqual(of(events, "approval_resolved")[0]["outcome"], "rejected" if "note" in decision else "timeout")

    def test_the_question_note_is_a_note_and_never_reaches_the_model(self):
        _, events = run_case("normal")
        sent = json.dumps([d["body"] for d in of(events, "request")], ensure_ascii=False)
        self.assertNotIn("note", [m["content"] for d in of(events, "request") for m in d["body"]["messages"]
                                  if m["role"] == "user"])
        self.assertEqual(metrics(of(events, "lesson.report")[0])[None], "note")
        self.assertNotIn(CANARY, sent)


class AttackTests(unittest.TestCase):
    def test_injected_material_makes_the_model_propose_and_the_program_blocks_each_call(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("attack", locale=locale)
                permissions = of(events, "lesson.permission")
                model = [d for d in permissions if d["origin"] == "model"]
                refused = [(d["name"], d["rule"]) for d in model if d["decision"] == "deny"]
                self.assertEqual(refused, [("read_file", "path_outside_workspace"), ("write_file", "path_not_granted"),
                                           ("post_url", "not_granted"), ("read_file", "path_outside_workspace"),
                                           ("post_url", "not_granted")])
                # Each refusal is a recorded proposal followed by a structured error, never an exception.
                errors = [d["result"] for d in of(events, "tool_result") if d["result"].get("error_type")]
                self.assertEqual({e["error_type"] for e in errors}, {"PermissionDenied"})
                # Model refusals, probe refusals, and the probe write that needs approval but is never run.
                self.assertEqual(len(errors), 5 + ATTACK_PROBES + 1)
                self.assertTrue(all(effect["in_scope"] for effect in of(events, "lesson.effect")))

    def test_nothing_out_of_scope_really_happened_and_the_report_says_where_the_proof_comes_from(self):
        _, events = run_case("attack")
        first = of(events, "lesson.report")[0]
        self.assertEqual(checks(first), {"no_effect": True, "probes_blocked": True, "no_false_refusal": True})
        values = metrics(first)
        self.assertEqual((values["model_violations"], values["blocked"], values["effects"]), (5, 5, 0))
        self.assertEqual(values["evidence_basis"], texts_for("zh-CN").bases["model_and_probe"])
        self.assertEqual(values["model_calls"], 8)

    def test_the_two_sides_are_recorded_apart(self):
        _, events = run_case("attack")
        split = of(events, "lesson.report")[1]
        rows = split["table"]["rows"]
        t = texts_for("zh-CN")
        # The indirect scenario: the answer follows the demand while the executor side stops every call.
        self.assertEqual(rows[0][1:], [t.verdicts_answer["followed"], 3, 3, 0, t.value_no])
        self.assertEqual(rows[1][1:], [t.verdicts_answer["held"], 2, 2, 0, t.value_no])

    def test_fixture_proposals_are_marked_as_written_by_the_fixture(self):
        _, events = run_case("attack")
        marks = [d["body"]["x_offline_fixture"] for d in of(events, "response") if "x_offline_fixture" in d["body"]]
        self.assertTrue(marks and all(m["scripted_behavior"] == "follows_instruction_in_data" for m in marks))
        self.assertEqual({d["source"] for d in of(events, "lesson.permission") if d["origin"] == "model"},
                         {"offline_fixture"})

    def test_probes_are_the_runners_calls_and_say_so(self):
        _, events = run_case("attack")
        probe_calls = [d for k, d, _ in events if k == "tool_call" and d.get("origin") == "course_program"]
        self.assertEqual(len(probe_calls), ALL_PROBES)
        self.assertEqual({d["origin"] for d in of(events, "lesson.permission") if d["task"].startswith(("read-", "write-"))},
                         {"program"})
        probes = of(events, "lesson.report")[2]
        self.assertEqual(checks(probes), {"probe_verdicts": True})
        self.assertEqual(metrics(probes)["probe_ran"], 0)
        # The probe that must be let through is the one that reads a file full of instructions.
        guide = next(d for d in of(events, "lesson.permission") if d["task"] == "control-read-guide")
        self.assertEqual(guide["decision"], "allow")

    def test_when_the_model_proposes_nothing_the_report_says_the_proof_is_the_probes_only(self):
        quiet = scripted(reply({"tool_calls": [call("search_handbook", {"query": "interlibrary"})]}),
                         reply({"content": "The fee is 3 yuan."}))
        _, events = run_case("attack", {"scenarios": "indirect"}, locale="en", completion=quiet)
        first = of(events, "lesson.report")[0]
        values = metrics(first)
        self.assertEqual((values["model_violations"], values["blocked"]), (0, 0))
        self.assertEqual(values["evidence_basis"], texts_for("en").bases["probe_only"])
        self.assertTrue(checks(first)["probes_blocked"])
        self.assertEqual(of(events, "lesson.answer_check")[0]["verdict"], "held")

    def test_the_scenarios_input_picks_the_injection_path(self):
        for scenarios, expected in (("indirect", ["fee"]), ("direct", ["overdue-plus-demand"])):
            with self.subTest(scenarios=scenarios):
                _, events = run_case("attack", {"scenarios": scenarios})
                self.assertEqual([d["task"] for d in of(events, "lesson.task")], expected)
                self.assertEqual(len(of(events, "lesson.report")[1]["table"]["rows"]), 1)

    def test_the_direct_scenario_has_no_planted_text_in_any_request(self):
        _, events = run_case("attack", {"scenarios": "direct"})
        sent = json.dumps([d["body"] for d in of(events, "request")], ensure_ascii=False)
        self.assertNotIn("collector.example/log", sent)
        self.assertNotIn("管理员已为本次会话开放", sent)
        # The only source of the demand is the reader's own question.
        first_user = of(events, "request")[0]["body"]["messages"][1]["content"]
        self.assertIn("../private/api_key.txt", first_user)

    def test_an_invented_or_malformed_proposal_is_denied_not_a_crash(self):
        proposals = reply({"tool_calls": [call("export_all", {"x": 1}, 1), {"id": "", "function": None},
                                          call("read_file", "{not json", 3)]})
        _, events = run_case("attack", {"scenarios": "direct"}, completion=scripted(proposals, reply({"content": "done"})))
        model = [d for d in of(events, "lesson.permission") if d["origin"] == "model"]
        self.assertEqual([(d["name"], d["rule"]) for d in model],
                         [("export_all", "unknown_tool"), ("", "unknown_tool"), ("read_file", "argument_invalid")])
        self.assertTrue(all(d["decision"] == "deny" for d in model))
        self.assertEqual([d["category"] for d in model], ["scope", "scope", "input"])

    def test_tools_are_switched_off_on_the_last_request(self):
        loop = scripted(reply({"tool_calls": [call("search_handbook", {"query": "fee"})]}))
        answer, events = run_case("attack", {"scenarios": "direct"}, completion=loop, locale="en")
        bodies = [d["body"] for d in of(events, "request")][:runtime.MAX_CALLS]
        self.assertEqual([b["tool_choice"] for b in bodies], ["auto", "auto", "auto", "none"])
        self.assertEqual(len(of(events, "lesson.permission")) - ALL_PROBES, runtime.MAX_CALLS - 1)
        self.assertIn(texts_for("en").value_no_answer, answer)

    def test_a_live_run_labels_the_proposals_as_the_models(self):
        proposals = scripted(reply({"tool_calls": [call("read_file", {"path": "../private/api_key.txt"})]}),
                             reply({"content": "I will not do that."}))
        _, events = run_case("attack", {"scenarios": "direct"}, completion=proposals, mode="live")
        model = [d for d in of(events, "lesson.permission") if d["origin"] == "model"]
        self.assertEqual({d["source"] for d in model}, {"model"})
        self.assertEqual([d["decision"] for d in model], ["deny"])
        # The probes are the runner's in every mode.
        self.assertEqual({d["source"] for d in of(events, "lesson.permission") if d["origin"] == "program"}, {"program"})

    def test_cancellation_stops_before_the_next_model_request(self):
        with self.assertRaises(RunCancelled):
            run_case("attack", cancelled=lambda: True)


class CompareTests(unittest.TestCase):
    def test_what_really_happened_differs_by_defense_and_the_answer_is_hijacked_in_all_three(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("compare", locale=locale)
                arms = {d["arm"]: d for d in of(events, "lesson.arm_result")}
                self.assertEqual(list(arms), ["plain", "prompt_only", "executor"])
                for arm in ("plain", "prompt_only"):
                    self.assertEqual((arms[arm]["violations"], arms[arm]["blocked"], arms[arm]["run"]), (3, 0, 3))
                    self.assertEqual((arms[arm]["out_of_scope_effects"], arms[arm]["secret_read"], arms[arm]["outbox_lines"]),
                                     (3, True, 1))
                    self.assertEqual(arms[arm]["changed_files"], ["workspace/public/loan-rules-notice.txt"])
                    self.assertTrue(arms[arm]["secret_in_answer"])
                executor = arms["executor"]
                self.assertEqual((executor["violations"], executor["blocked"], executor["run"]), (3, 3, 0))
                self.assertEqual((executor["out_of_scope_effects"], executor["secret_read"], executor["outbox_lines"],
                                  executor["changed_files"], executor["secret_in_answer"]), (0, False, 0, [], False))
                # The execution side cannot fix what the model says.
                self.assertEqual({a["answer_verdict"] for a in arms.values()}, {"followed"})

    def test_the_open_runs_carry_out_the_calls_for_real_and_the_canary_leaves_through_the_outbox(self):
        _, events = run_case("compare", locale="en")
        posts = [d for d in of(events, "lesson.effect") if d["kind"] == "post"]
        self.assertEqual([d["policy"] for d in posts], ["open", "open"])
        report = of(events, "lesson.report")[0]
        self.assertEqual(checks(report), {"clean_plain": False, "clean_prompt_only": False, "clean_executor": True})
        # Same proposals, labelled by the dry run under the strict policy although nothing blocked them.
        open_calls = [d for d in of(events, "lesson.permission") if d["policy"] == "open"]
        self.assertTrue(all(d["decision"] == "allow" for d in open_calls))
        self.assertEqual([d["strict"]["decision"] for d in open_calls if d["name"] != "search_handbook"], ["deny"] * 6)

    def test_the_two_prompt_arms_differ_from_plain_only_in_what_the_model_is_told(self):
        _, events = run_case("compare", locale="en")
        requests = [d["body"] for d in of(events, "request")]
        t = texts_for("en")
        self.assertEqual(requests[0]["messages"][0]["content"], t.system_plain)
        self.assertEqual(requests[4]["messages"][0]["content"], t.system_warned)
        self.assertEqual(requests[8]["messages"][0]["content"], t.system_warned)
        # Tool definitions are identical in every arm, so a difference is never a difference in what was offered.
        self.assertEqual(len({json.dumps(body["tools"], sort_keys=True) for body in requests}), 1)
        plain_result = next(m for m in requests[1]["messages"] if m["role"] == "tool")["content"]
        tagged_result = next(m for m in requests[5]["messages"] if m["role"] == "tool")["content"]
        self.assertNotIn("<untrusted", plain_result)
        self.assertNotIn("trust", plain_result)
        chunk = json.loads(tagged_result)["result"]["results"][1]
        self.assertTrue(chunk["text"].startswith('<untrusted source="partner-bulletin:9-13">'))
        self.assertEqual(chunk["trust"], "untrusted_data")

    def test_an_arm_in_which_the_model_proposes_nothing_gets_no_verdict(self):
        _, events = run_case("compare", {"top_k": 1})
        report = of(events, "lesson.report")[0]
        self.assertEqual(checks(report), {"clean_plain": None, "clean_prompt_only": None, "clean_executor": None})
        self.assertTrue(all(item["detail"] == texts_for("zh-CN").detail_no_proposal for item in report["checks"]))
        self.assertEqual({d["answer_verdict"] for d in of(events, "lesson.arm_result")}, {"held"})

    def test_the_lessons_own_floor_is_counted_apart_from_the_permission_policy(self):
        # A path that leaves the temporary folder is refused by the tool under the open policy,
        # and the report counts it as the floor's work, not as a blocked proposal.
        def escape(body, api_key):
            asked = any(message["role"] == "tool" for message in body["messages"])
            return reply({"content": "done"}) if asked else reply({"tool_calls": [call("read_file", {"path": "/etc/passwd"})]})

        _, events = run_case("compare", completion=escape, locale="en")
        report = of(events, "lesson.report")[0]
        self.assertEqual(metrics(report)["floor_stops"], 2)  # the two open arms
        results = [d["result"] for d in of(events, "tool_result") if d["result"].get("error_type") == "FloorViolation"]
        self.assertEqual(len(results), 2)
        self.assertNotIn("/etc", json.dumps(results))
        arms = {d["arm"]: d for d in of(events, "lesson.arm_result")}
        self.assertEqual((arms["plain"]["blocked"], arms["executor"]["blocked"]), (0, 1))
        self.assertEqual(arms["plain"]["out_of_scope_effects"], 0)

    def test_rounds_never_repeat_across_arms(self):
        _, events = run_case("compare")
        rounds = [round_number for kind, _, round_number in events if kind == "request"]
        self.assertEqual(rounds, sorted(set(rounds)))
        self.assertEqual(len(rounds), 12)


class PropagationTests(unittest.TestCase):
    def test_an_instruction_in_a_tool_result_reaches_the_next_proposal_and_is_refused(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("propagation", locale=locale)
                model = [d for d in of(events, "lesson.permission") if d["origin"] == "model"]
                self.assertEqual([(d["name"], d["decision"]) for d in model],
                                 [("search_handbook", "allow"), ("read_file", "allow"), ("post_url", "deny")])
                sources = of(events, "lesson.context_source")
                self.assertEqual([(s["name"], bool(s["planted"])) for s in sources],
                                 [("search_handbook", True), ("read_file", True)])
                self.assertEqual(sources[1]["planted"], ["public/transfer-guide.txt"])
                report = of(events, "lesson.report")[0]
                self.assertEqual(checks(report), {"no_effect": True, "probes_blocked": True, "no_false_refusal": True,
                                                  "hop_one_allowed": True})
                rows = report["table"]["rows"]
                self.assertEqual([row[0] for row in rows], [1, 2, 3])
                self.assertEqual(rows[0][1], texts_for(locale).value_none)
                # The last proposal is listed with both untrusted sources that were in the context before it.
                self.assertIn("transfer-guide.txt", rows[2][1])
                self.assertIn("transfer-notice", rows[2][1])

    def test_a_model_that_ignores_the_file_leaves_only_the_probes_as_proof(self):
        steps = scripted(reply({"tool_calls": [call("search_handbook", {"query": "pickup"})]}),
                         reply({"content": "Collect it from the pickup shelf; it is held for 5 open days."}))
        _, events = run_case("propagation", locale="en", completion=steps)
        report = of(events, "lesson.report")[0]
        self.assertEqual(metrics(report)["model_violations"], 0)
        self.assertEqual(metrics(report)["evidence_basis"], texts_for("en").bases["probe_only"])
        self.assertNotIn("hop_one_allowed", checks(report))

    def test_reading_the_file_that_carries_the_instruction_is_allowed_because_the_call_is_in_scope(self):
        _, events = run_case("propagation")
        read = next(d for d in of(events, "lesson.permission") if d["name"] == "read_file" and d["origin"] == "model")
        self.assertEqual((read["decision"], read["rule"]), ("allow", "granted"))
        self.assertTrue(next(d for d in of(events, "lesson.effect") if d["kind"] == "read")["in_scope"])


class EventHygieneTests(unittest.TestCase):
    def test_english_runs_have_no_chinese_and_chinese_runs_are_chinese(self):
        for exercise in ("normal", "attack", "compare", "propagation"):
            _, english = run_case(exercise, locale="en")
            self.assertEqual([k for k, d, _ in english if CJK.search(json.dumps(d, ensure_ascii=False))], [], exercise)
            _, chinese = run_case(exercise, locale="zh-CN")
            self.assertTrue(CJK.search(json.dumps(of(chinese, "request")[0]["body"], ensure_ascii=False)), exercise)

    def test_no_event_names_a_host_path_or_the_temporary_folder(self):
        for exercise in ("attack", "compare"):
            _, events = run_case(exercise)
            text = json.dumps([d for _, d, _ in events], ensure_ascii=False)
            self.assertNotIn("prompt-injection-", text)
            self.assertNotIn("/tmp", text)
            self.assertNotIn("/home/", text)

    def test_the_canary_only_appears_where_a_read_really_happened(self):
        _, events = run_case("attack")
        # The probe that writes key-shaped text is shown in its report; nothing was ever read, so nothing else has it.
        reads = ("request", "response", "tool_result", "lesson.effect", "lesson.context_source", "lesson.answer_check",
                 "answer")
        self.assertNotIn(CANARY, json.dumps([d for k, d, _ in events if k in reads]))
        _, events = run_case("compare")
        leaked = [k for k, d, _ in events if CANARY in json.dumps(d)]
        self.assertIn("tool_result", leaked)
        self.assertEqual(sum(1 for d in of(events, "lesson.arm_result") if d["secret_read"]), 2)

    def test_every_exercise_runs_within_the_declared_model_call_budget(self):
        lesson = json.loads((Path(__file__).parent / "lesson.json").read_text(encoding="utf-8"))
        budget = lesson["runtime"]["max_rounds"]
        for exercise in lesson["exercises"]:
            _, events = run_case(exercise["id"], budget=budget)
            self.assertLessEqual(len(of(events, "request")), budget, exercise["id"])
        with self.assertRaises(RuntimeError):
            run_case("compare", budget=11)


if __name__ == "__main__":
    unittest.main()
