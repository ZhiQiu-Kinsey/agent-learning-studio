"""Behavior tests for hooks-approval: scripted model data and stand-in approvers, real tools on a real desk.

Nothing here talks to a model. The "model" follows a script and the approvals come from a stand-in
policy (decided_by: offline_fixture) or from a gate function that plays the page (decided_by: learner).
What they decide is fixed; what the hooks, the gate and the tools do with it is real: the desk is a
temporary directory, and every claim about "did not run" or "ran with these arguments" is checked
against the files and the digests.
"""
import json
import re
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from course.execution import RunContext, approval_digest, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_hooks_approval import runtime
from lessons.lesson_hooks_approval.fixtures import OUTSIDE_RECIPIENT, create_approval_policy, create_completion
from lessons.lesson_hooks_approval.gate import ARGUMENT_MODELS
from lessons.lesson_hooks_approval.hooks import (
    ALLOW, PRE_HOOKS, Hook, HookResult, field_allowlist, mask_email, mask_phone, normalize_arguments, post_hooks,
    recipient_domain, record_scope, risk_level, run_post_hooks, run_pre_hooks)
from lessons.lesson_hooks_approval.locales import texts_for
from lessons.lesson_hooks_approval.store import SEED, Desk, DeskError
from server.offline import tool_call

ZH = texts_for("zh-CN")
EN = texts_for("en")
CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
APPROVE = lambda request: {"decision": "approve"}  # noqa: E731 - a stand-in for the learner
TASK_OF = {"approve-write": "approve_write", "reject-timeout": "reject_timeout", "edit-recheck": "edit_recheck",
           "swap-guard": "swap_guard"}


def reply(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


def scripted(calls, final="done"):
    """A model that proposes `calls` (tool, arguments) one by one and then replies `final`."""
    def complete(body, api_key):
        step = sum(1 for message in body["messages"] if message["role"] == "tool")
        if step >= len(calls):
            return reply(final)
        message = {"role": "assistant", "content": None,
                   "tool_calls": [tool_call(calls[step][0], calls[step][1], step + 1)]}
        return {"choices": [{"message": message, "finish_reason": "tool_calls"}]}
    return complete


PRESETS = {"edit-recheck": {"allow_edit": True}, "swap-guard": {"late_rewrite": True}}  # as in lesson.json


def run_case(exercise_id, inputs=None, completion=None, approval=None, gate=None, budget=10, cancelled=lambda: False,
             locale="zh-CN", with_policy=True):
    """Run the lesson offline. Returns (answer, events).

    run_case.desks holds the desk objects (alive during the run); run_case.final[0] is the desk's records and
    outbox read just before its directory is deleted, also when the run ends in RunCancelled.
    """
    events, desks, final = [], [], []

    class Recorded(Desk):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            desks.append(self)

    class Directory(tempfile.TemporaryDirectory):
        def cleanup(self):
            if desks and not final:
                final.append({"records": desks[-1].records(), "outbox": desks[-1].outbox()})
            super().cleanup()

    values = validate_inputs(runtime, {"task": TASK_OF.get(exercise_id, "approve_write"),
                                       **PRESETS.get(exercise_id, {}), **(inputs or {})})
    context = RunContext(
        lesson_id="hooks-approval", exercise_id=exercise_id, question="", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale, approval_gate=gate,
        approval_policy=(approval or create_approval_policy(exercise_id, values, locale)) if with_policy else None)
    run_case.desks, run_case.final, run_case.events = desks, final, events
    with patch.object(runtime, "Desk", Recorded), patch.object(runtime.tempfile, "TemporaryDirectory", Directory):
        answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def kinds(events):
    return [event for event, _, _ in events]


def results(events):
    """The gate results (the dict inside tool_result) in order."""
    return [data["result"]["result"] for data in of(events, "tool_result")]


def ledger_report(events):
    return next(data for data in of(events, "lesson.report") if any(m["id"] == "tool-calls" for m in data["metrics"]))


def effects_report(events):
    return next(data for data in of(events, "lesson.report") if any(m["id"] == "records-changed" for m in data["metrics"]))


def item(data, kind, item_id):
    return next(entry for entry in data[kind] if entry["id"] == item_id)


class InputTests(unittest.TestCase):
    def test_defaults_and_bounds(self):
        self.assertEqual(validate_inputs(runtime, {}), {"task": "approve_write", "approval_timeout_s": 30,
                                                        "allow_edit": False, "late_rewrite": False})
        for bad in ({"task": "delete_all"}, {"approval_timeout_s": 2}, {"approval_timeout_s": 301},
                    {"allow_edit": "yes please"}, {"unknown": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_every_task_and_message_exists_in_both_languages(self):
        for texts in (ZH, EN):
            self.assertEqual(set(texts.tasks), {"approve_write", "reject_timeout", "edit_recheck", "swap_guard"})
            self.assertEqual(set(texts.refusals), set(texts.refusal_labels))
        self.assertEqual(set(ZH.refusals), set(EN.refusals))
        self.assertEqual(set(ZH.hook_reasons), set(EN.hook_reasons))

    def test_tool_definitions_match_the_argument_models(self):
        for locale in ("zh-CN", "en"):
            for definition in runtime.tool_definitions(locale):
                function = definition["function"]
                model = ARGUMENT_MODELS[function["name"]]
                self.assertEqual(set(function["parameters"]["properties"]), set(model.model_fields))
                self.assertEqual(function["parameters"]["required"], list(model.model_fields))
                self.assertFalse(function["parameters"]["additionalProperties"])


class DeskTests(unittest.TestCase):
    """The tools are real: a write changes a file, and the snapshot proves it."""

    def setUp(self):
        from pathlib import Path
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.desk = Desk(Path(directory.name), {record[0]: "title " + record[0] for record in SEED})

    def test_reads_change_nothing_and_writes_change_the_snapshot(self):
        start = self.desk.snapshot()
        self.assertEqual(len(self.desk.list_records()), 4)
        self.assertEqual(self.desk.read_record("TKT-101")["owner_email"], "alice@corp.example")
        self.assertEqual(self.desk.snapshot(), start)
        self.assertEqual(self.desk.update_record("TKT-101", "status", "resolved"),
                         {"record_id": "TKT-101", "field": "status", "before": "open", "after": "resolved"})
        after_update = self.desk.snapshot()
        self.assertNotEqual(after_update, start)
        notice = self.desk.send_notice("alice@corp.example", "s", "b")
        self.assertEqual((notice["notice_id"], self.desk.outbox()), ("N-001", [notice]))
        self.assertNotEqual(self.desk.snapshot(), after_update)
        self.assertEqual(self.desk.send_notice("alice@corp.example", "s", "b")["notice_id"], "N-002")

    def test_errors_are_structured_and_paths_cannot_escape(self):
        for record_id in ("TKT-999", "../outbox", "../../etc/passwd", ""):
            with self.subTest(record_id=record_id), self.assertRaises(DeskError) as caught:
                self.desk.read_record(record_id)
            self.assertEqual(caught.exception.code, "record_not_found")
        with self.assertRaises(DeskError) as caught:
            self.desk.update_record("TKT-101", "owner", "mallory")
        self.assertEqual(caught.exception.code, "unknown_owner")


class HookTests(unittest.TestCase):
    def test_normalize_rewrites_and_leaves_clean_arguments_alone(self):
        result = normalize_arguments("send_notice", {"recipient": " Alice@Corp.Example ", "subject": "s", "body": "b"})
        self.assertEqual((result.verdict, result.arguments["recipient"]), ("rewrite", "alice@corp.example"))
        status = normalize_arguments("update_record", {"record_id": "tkt-1 ", "field": "Status", "value": " Resolved"})
        self.assertEqual(status.arguments, {"record_id": "TKT-1", "field": "status", "value": "resolved"})
        note = normalize_arguments("update_record", {"record_id": "TKT-101", "field": "note", "value": " Keep Case "})
        self.assertEqual(note, ALLOW)  # a note keeps its case and its spaces: only status values are normalized
        self.assertEqual(normalize_arguments("read_record", {"record_id": "TKT-101"}), ALLOW)

    def test_deny_rules(self):
        self.assertEqual(record_scope("read_record", {"record_id": "../x"}).reason, "record_id_format")
        self.assertEqual(record_scope("read_record", {"record_id": "TKT-12"}).verdict, "deny")
        self.assertEqual(record_scope("read_record", {"record_id": "TKT-102"}), ALLOW)
        for recipient in ("eve@evil.example", "alice@corp.example.evil.example", "@corp.example", "alice", "a b@corp.example"):
            with self.subTest(recipient=recipient):
                self.assertEqual(recipient_domain("send_notice", {"recipient": recipient}).reason, "recipient_outside_domain")
        self.assertEqual(recipient_domain("send_notice", {"recipient": "alice@corp.example"}), ALLOW)
        self.assertEqual(field_allowlist("update_record", {"record_id": "TKT-101", "field": "customer_phone",
                                                           "value": "1"}).reason, "field_not_allowed")
        self.assertEqual(field_allowlist("update_record", {"record_id": "TKT-101", "field": "status",
                                                           "value": "done"}).reason, "status_not_allowed")

    def test_risk_levels(self):
        def ask(tool, **arguments):
            return risk_level(tool, arguments)
        self.assertEqual(ask("list_records"), ALLOW)
        self.assertEqual(ask("read_record", record_id="TKT-101"), ALLOW)
        self.assertEqual(ask("update_record", field="note", value="x").risk, "medium")
        self.assertEqual(ask("update_record", field="status", value="resolved").risk, "medium")
        self.assertEqual(ask("update_record", field="status", value="closed").risk, "high")
        self.assertEqual(ask("update_record", field="owner", value="bob").risk, "high")
        self.assertEqual(ask("send_notice", recipient="alice@corp.example").risk, "high")
        self.assertEqual(ask("send_notice", recipient="all@corp.example").risk, "critical")
        # A tool nobody classified is denied, not waved through.
        self.assertEqual((ask("drop_table").verdict, ask("drop_table").reason), ("deny", "tool_not_classified"))

    def test_hook_results_are_validated(self):
        for bad in (dict(verdict="maybe"), dict(verdict="rewrite"), dict(verdict="allow", arguments={}),
                    dict(verdict="ask"), dict(verdict="ask", risk="extreme"), dict(verdict="deny", risk="low")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                HookResult(**bad)

    def test_chain_semantics(self):
        seen = []

        def spy(name, result):
            def run(tool, arguments):
                seen.append((name, dict(arguments)))
                return result
            return Hook(name, run)

        rewrite = HookResult("rewrite", "r", arguments={"value": "b"})
        outcome = run_pre_hooks((spy("one", rewrite), spy("two", ALLOW)), "t", {"value": "a"})
        # A rewrite feeds its arguments to the next hook and ends up in the outcome.
        self.assertEqual((outcome.verdict, outcome.arguments, seen[1][1]), ("allow", {"value": "b"}, {"value": "b"}))
        self.assertEqual(outcome.changes, [{"field": "value", "before": "a", "after": "b"}])
        # Deny stops the chain: the hooks after it never see the call.
        seen.clear()
        denied = run_pre_hooks((spy("one", HookResult("deny", "no")), spy("two", ALLOW)), "t", {})
        self.assertEqual((denied.verdict, denied.hook, denied.reason, [name for name, _ in seen]), ("deny", "one", "no", ["one"]))
        # Several asks keep the highest risk, whatever the order.
        asks = run_pre_hooks((spy("a", HookResult("ask", risk="high")), spy("b", HookResult("ask", risk="medium"))), "t", {})
        self.assertEqual((asks.verdict, asks.risk), ("ask", "high"))

    def test_order_matters_normalize_before_the_rules(self):
        arguments = {"recipient": "Alice@Corp.Example", "subject": "s", "body": "b"}
        sensible = run_pre_hooks(PRE_HOOKS, "send_notice", arguments)
        self.assertEqual((sensible.verdict, sensible.arguments["recipient"]), ("ask", "alice@corp.example"))
        swapped = (PRE_HOOKS[2], PRE_HOOKS[0], *PRE_HOOKS[1:2], *PRE_HOOKS[3:])
        wrong = run_pre_hooks(swapped, "send_notice", arguments)
        self.assertEqual((wrong.verdict, wrong.hook), ("deny", "recipient_domain"))  # a valid address refused for its case

    def test_masking(self):
        self.assertEqual(mask_phone("13800001111"), "138****1111")
        self.assertEqual(len(mask_phone("13800001111")), 11)
        self.assertEqual(mask_email("li.wei@customer.example"), "l***@customer.example")
        self.assertEqual(mask_phone("123"), "***")

    def test_post_hooks_redact_verify_and_record(self):
        from pathlib import Path
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        desk = Desk(Path(directory.name), {record[0]: "t" for record in SEED})
        hooks = post_hooks(desk)
        data, steps, info = run_post_hooks(hooks, "read_record", {"record_id": "TKT-101"}, desk.read_record("TKT-101"))
        self.assertEqual(info["redacted"], ["customer_email", "customer_phone"])
        self.assertNotIn("13800001111", json.dumps(data))
        self.assertEqual([step["id"] for step in steps], ["redact_customer_data", "verify_effect", "audit_trail"])
        self.assertEqual(info["result_digest"], approval_digest({"data": data}))
        # verify_effect reads the file back: a write that did not land is reported, not trusted.
        arguments = {"record_id": "TKT-101", "field": "status", "value": "closed"}
        _, _, ok = run_post_hooks(hooks, "update_record", arguments, {})
        self.assertFalse(ok["verified"])
        desk.update_record(**arguments)
        _, _, ok = run_post_hooks(hooks, "update_record", arguments, {})
        self.assertTrue(ok["verified"])


class ApprovedWriteTests(unittest.TestCase):
    """approve-write: reads run at once, each write waits for a decision, and the decision's arguments are the ones that run."""

    def test_the_full_path_in_event_order(self):
        answer, events = run_case("approve-write")
        types = kinds(events)
        # list_records and read_record: hooks, no approval.
        self.assertEqual(types.count("approval_requested"), 2)
        update_calls = [index for index, (kind, data, _) in enumerate(events)
                        if kind == "tool_call" and data["function"]["name"] == "update_record"]
        window = types[update_calls[0]:update_calls[0] + 7]
        self.assertEqual(window, ["tool_call", "lesson.hook_pre", "approval_requested", "approval_resolved",
                                  "lesson.guard", "lesson.hook_post", "tool_result"])
        requested = of(events, "approval_requested")
        self.assertEqual([data["kind"] for data in requested], ["tool.update_record", "tool.send_notice"])
        self.assertEqual([data["risk"] for data in requested], ["medium", "high"])
        # The card shows the normalized arguments: the model wrote " Alice@Corp.Example ", the notice goes to the clean address.
        self.assertEqual(requested[1]["payload"]["arguments"]["recipient"], "alice@corp.example")
        self.assertEqual(run_case.final[0]["outbox"][0]["recipient"], "alice@corp.example")
        self.assertEqual(run_case.final[0]["records"]["TKT-102"]["status"], "resolved")
        self.assertEqual({data["decided_by"] for data in of(events, "approval_resolved")}, {"offline_fixture"})
        self.assertIn("2", answer.splitlines()[0])
        self.assertTrue(all(result["ok"] and result["executed"] for result in results(events)))

    def test_nothing_runs_before_the_decision(self):
        seen = []

        def policy(request):
            desk = run_case.desks[0]
            seen.append((request["kind"], desk.records()["TKT-102"]["status"], desk.outbox()))
            return {"decision": "approve"}

        run_case("approve-write", approval=policy)
        # While the card was waiting, the status was still the old one and the outbox still empty.
        self.assertEqual(seen, [("tool.update_record", "in_progress", []), ("tool.send_notice", "resolved", [])])
        report = ledger_report(run_case.events)
        self.assertTrue(item(report, "checks", "no-early-effect")["passed"])

    def test_the_ledger_report_checks_and_digests(self):
        _, events = run_case("approve-write")
        report = ledger_report(events)
        for check_id in ("no-early-effect", "args-match-approval", "summary-covers-args", "customer-data-redacted"):
            self.assertTrue(item(report, "checks", check_id)["passed"], check_id)
        self.assertNotIn("passed", item(report, "checks", "refused-not-executed"))  # nothing refused: no verdict
        rows = report["table"]["rows"]
        self.assertEqual([row[1] for row in rows], ["list_records", "read_record", "update_record", "send_notice"])
        self.assertEqual(rows[2][6], rows[2][7])  # approved digest equals executed digest
        self.assertTrue(rows[2][6].startswith("sha256:"))
        self.assertEqual((rows[0][6], rows[0][7]), ("—", "—"))  # a read has neither
        metrics = {m["id"]: m["value"] for m in report["metrics"]}
        self.assertEqual((metrics["tool-calls"], metrics["ran-without-approval"], metrics["approved"]), (4, 2, 2))
        self.assertTrue(item(effects_report(events), "checks", "effects-match-ledger")["passed"])

    def test_digests_in_events_agree_with_each_other(self):
        _, events = run_case("approve-write")
        for requested, resolved, guard in zip(of(events, "approval_requested"), of(events, "approval_resolved"),
                                              of(events, "lesson.guard")):
            self.assertEqual(requested["payload_digest"], approval_digest(requested["payload"]))
            self.assertEqual(resolved["payload_digest"], requested["payload_digest"])
            self.assertEqual((guard["approved_digest"], guard["attempted_digest"], guard["match"]),
                             (requested["payload_digest"], requested["payload_digest"], True))

    def test_the_page_decides_in_a_live_like_run(self):
        waited = []

        def page(request, timeout_s):
            waited.append((request["approval_id"], timeout_s, run_case.desks[0].outbox()))
            return {"decision": "approve", "note": "checked"}

        _, events = run_case("approve-write", gate=page, with_policy=False, inputs={"approval_timeout_s": 45})
        self.assertEqual([entry[1] for entry in waited], [45, 45])
        self.assertEqual({data["decided_by"] for data in of(events, "approval_resolved")}, {"learner"})
        self.assertEqual(waited[1][2], [])
        self.assertEqual(len(run_case.final[0]["outbox"]), 1)


class RefusedWriteTests(unittest.TestCase):
    def test_rejection_does_not_execute_and_the_model_reads_the_note(self):
        answer, events = run_case("reject-timeout")
        rejected = [result for result in results(events) if result.get("error_type") == "approval_rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual((rejected[0]["executed"], rejected[0]["note"]), (False, ZH.script_reject_note))
        self.assertIn(ZH.script_reject_note, rejected[0]["error"])
        # The model's next request carries that result, and its next proposal is a different call (the owner only).
        request = of(events, "request")[3]["body"]["messages"][-1]
        self.assertEqual(json.loads(request["content"])["result"]["error_type"], "approval_rejected")
        proposals = [json.loads(data["function"]["arguments"]) for data in of(events, "tool_call")
                     if data["function"]["name"] == "send_notice"]
        self.assertEqual([item_["recipient"] for item_ in proposals], ["all@corp.example", "bob@corp.example"])
        self.assertEqual(run_case.final[0]["outbox"], [])  # neither notice went out

    def test_timeout_counts_as_a_rejection_with_its_own_error_type(self):
        _, events = run_case("reject-timeout")
        timed_out = [result for result in results(events) if result.get("error_type") == "approval_timeout"]
        self.assertEqual(len(timed_out), 1)
        self.assertEqual(timed_out[0]["executed"], False)
        self.assertNotIn("note", timed_out[0])
        resolved = of(events, "approval_resolved")
        self.assertEqual([(data["outcome"], data["decided_by"]) for data in resolved],
                         [("approved", "offline_fixture"), ("rejected", "offline_fixture"), ("timeout", "timeout")])

    def test_the_run_ends_honestly_and_says_why(self):
        answer, events = run_case("reject-timeout")
        report = ledger_report(events)
        self.assertTrue(item(report, "checks", "refused-not-executed")["passed"])
        self.assertTrue(item(report, "checks", "no-early-effect")["passed"])
        metrics = {m["id"]: m["value"] for m in report["metrics"]}
        self.assertEqual((metrics["rejected"], metrics["timeouts"], metrics["approved"]), (1, 1, 1))
        lines = answer.splitlines()
        self.assertIn(ZH.answer_refused_head, lines)
        self.assertIn(ZH.answer_refused_line.format(n=3, tool="send_notice", reason=ZH.refusal_labels["approval_rejected"].format(hook="")), lines)
        self.assertIn(ZH.refusal_labels["approval_timeout"], answer)
        # What the desk shows: the status change went through, no notice did.
        self.assertEqual(effects_report(events)["table"]["rows"], [[ZH.kind_record, "TKT-103.status", "open", "resolved"]])
        self.assertEqual(run_case.final[0]["records"]["TKT-103"]["status"], "resolved")

    def test_a_rejection_with_no_note_still_gives_the_model_a_reason(self):
        completion = scripted([("send_notice", {"recipient": "bob@corp.example", "subject": "s", "body": "b"})])
        _, events = run_case("approve-write", completion=completion, approval=lambda request: {"decision": "reject"})
        self.assertEqual(results(events)[0]["note"], ZH.no_note)

    def test_stop_during_the_wait_still_prevents_the_side_effect(self):
        state = {"stop": False}

        def policy(request):
            state["stop"] = True  # the Stop button is pressed while the card is open
            return {"decision": "approve"}

        completion = scripted([("send_notice", {"recipient": "bob@corp.example", "subject": "s", "body": "b"})])
        with self.assertRaises(RunCancelled):
            run_case("approve-write", completion=completion, approval=policy, cancelled=lambda: state["stop"])
        self.assertEqual(run_case.final[0]["outbox"], [])


class HookDeniedTests(unittest.TestCase):
    """Rules deny before anyone is asked: no card, no execution, and a reason the model can act on."""

    def run_calls(self, calls, **kwargs):
        return run_case("approve-write", completion=scripted(calls), approval=kwargs.pop("approval", APPROVE), **kwargs)

    def test_each_deny_rule_stops_the_call_without_an_approval_card(self):
        cases = [
            ("send_notice", {"recipient": "eve@evil.example", "subject": "s", "body": "b"}, "recipient_domain"),
            ("read_record", {"record_id": "../outbox"}, "record_scope"),
            ("update_record", {"record_id": "TKT-101", "field": "customer_phone", "value": "1"}, "field_allowlist"),
            ("update_record", {"record_id": "TKT-101", "field": "status", "value": "deleted"}, "field_allowlist"),
        ]
        for tool, arguments, hook in cases:
            with self.subTest(hook=hook, arguments=arguments):
                _, events = self.run_calls([(tool, arguments)], approval=lambda request: self.fail("asked a person"))
                result = results(events)[0]
                self.assertEqual((result["ok"], result["executed"], result["error_type"], result["hook"]),
                                 (False, False, "hook_denied", hook))
                self.assertEqual(result["phase"], "pre")
                self.assertNotIn("approval_requested", kinds(events))
                self.assertEqual(run_case.final[0]["outbox"], [])
                pre = of(events, "lesson.hook_pre")[0]
                self.assertEqual(pre["denied_by"], hook)
                # The chain stopped at the denying hook: the hooks after it have no step.
                self.assertEqual(pre["steps"][-1]["id"], hook)

    def test_a_hook_that_rewrites_is_visible_even_on_a_read(self):
        _, events = self.run_calls([("read_record", {"record_id": " tkt-101 "})])
        pre = of(events, "lesson.hook_pre")[0]
        self.assertEqual(pre["changes"], [{"field": "record_id", "before": " tkt-101 ", "after": "TKT-101"}])
        self.assertEqual(json.loads(of(events, "tool_call")[0]["function"]["arguments"])["record_id"], " tkt-101 ")
        self.assertTrue(results(events)[0]["ok"])

    def test_invalid_arguments_are_a_structured_error_before_any_hook(self):
        _, events = self.run_calls([("send_notice", {"recipient": "bob@corp.example", "subject": "s", "body": "b",
                                                    "cc": "all@corp.example"}),
                                    ("update_record", {"record_id": "TKT-101"}),
                                    ("read_record", {"record_id": 101})])
        self.assertEqual([result["error_type"] for result in results(events)], ["invalid_arguments"] * 3)
        self.assertEqual(results(events)[0]["fields"], "cc")
        self.assertEqual(results(events)[1]["fields"], "field, value")
        self.assertNotIn("lesson.hook_pre", kinds(events))

    def test_an_unregistered_tool_never_runs(self):
        _, events = self.run_calls([("drop_database", {})])
        result = of(events, "tool_result")[0]["result"]
        self.assertFalse(result["ok"])
        self.assertNotIn("lesson.hook_pre", kinds(events))

    def test_approval_does_not_promise_success(self):
        _, events = self.run_calls([("update_record", {"record_id": "TKT-999", "field": "status", "value": "closed"})])
        result = results(events)[0]
        self.assertEqual((result["ok"], result["executed"], result["error_type"]), (False, True, "record_not_found"))
        self.assertEqual(result["approval"]["outcome"], "approved")
        self.assertEqual(of(events, "approval_requested")[0]["risk"], "high")  # closing is high risk


class EditedApprovalTests(unittest.TestCase):
    """An edited payload is new input: it goes through the deny rules again, and what runs is what was typed."""

    def edit(self, payload):
        return lambda request: {"decision": "approve", "edited_payload": payload}

    def run_edit(self, payload, **kwargs):
        completion = scripted([("send_notice", {"recipient": "carol@corp.example", "subject": "s", "body": "b"})])
        return run_case("edit-recheck", completion=completion, approval=self.edit(payload), **kwargs)

    def test_an_out_of_bounds_edit_is_stopped_by_the_same_rule(self):
        answer, events = run_case("edit-recheck")
        resolved = of(events, "approval_resolved")[0]
        self.assertEqual((resolved["outcome"], resolved["edited"]), ("approved", True))
        self.assertEqual(resolved["payload"]["arguments"]["recipient"], OUTSIDE_RECIPIENT)
        recheck = of(events, "lesson.hook_recheck")[0]
        self.assertEqual((recheck["verdict"], recheck["denied_by"]), ("deny", "recipient_domain"))
        self.assertEqual(recheck["edited_fields"], [{"field": "recipient", "before": "carol@corp.example", "after": OUTSIDE_RECIPIENT}])
        result = results(events)[-1]
        self.assertEqual((result["error_type"], result["phase"], result["hook"], result["executed"]),
                         ("hook_denied", "recheck", "recipient_domain", False))
        # The message the model reads names the edited field, not only the rule that fired.
        self.assertEqual(result["fields"], "recipient")
        self.assertIn("recipient", result["error"])
        self.assertEqual(run_case.final[0]["outbox"], [])
        self.assertNotIn("lesson.guard", kinds(events))
        self.assertTrue(item(ledger_report(events), "checks", "refused-not-executed")["passed"])

    def test_the_card_is_editable_only_when_the_input_says_so(self):
        _, events = run_case("edit-recheck")
        self.assertTrue(of(events, "approval_requested")[0]["editable"])
        _, events = run_case("approve-write")
        self.assertFalse(any(data["editable"] for data in of(events, "approval_requested")))
        # The platform refuses an edit on a card that was not editable; the refusal reaches the model as an
        # error result, and nothing runs.
        completion = scripted([("send_notice", {"recipient": "bob@corp.example", "subject": "s", "body": "b"})])
        _, events = run_case("approve-write", completion=completion, approval=self.edit(
            {"tool": "send_notice", "arguments": {"recipient": "bob@corp.example", "subject": "s", "body": "b"}}))
        outer = of(events, "tool_result")[0]["result"]
        self.assertEqual((outer["ok"], outer["error_type"]), (False, "ValueError"))
        self.assertEqual(run_case.final[0]["outbox"], [])

    def test_an_in_bounds_edit_runs_exactly_as_typed(self):
        edited = {"tool": "send_notice", "arguments": {"recipient": "bob@corp.example", "subject": "edited", "body": "typed by hand"}}
        _, events = self.run_edit(edited, inputs={"allow_edit": True})
        self.assertEqual(run_case.final[0]["outbox"][0]["subject"], "edited")
        self.assertEqual(run_case.final[0]["outbox"][0]["recipient"], "bob@corp.example")
        resolved = of(events, "approval_resolved")[0]
        guard = of(events, "lesson.guard")[0]
        self.assertEqual((guard["approved_digest"], guard["attempted_digest"]), (resolved["payload_digest"],) * 2)
        self.assertNotEqual(resolved["payload_digest"], resolved["requested_digest"])
        report = ledger_report(events)
        self.assertTrue(item(report, "checks", "args-match-approval")["passed"])
        self.assertEqual(report["table"]["rows"][0][5:6], [ZH.cell_executed])
        self.assertIn(ZH.cell_edited, report["table"]["rows"][0][4])

    def test_an_edit_that_would_be_rewritten_is_refused_instead_of_silently_changed(self):
        edited = {"tool": "send_notice", "arguments": {"recipient": "Bob@Corp.Example", "subject": "s", "body": "b"}}
        _, events = self.run_edit(edited, inputs={"allow_edit": True})
        result = results(events)[0]
        self.assertEqual((result["error_type"], result["fields"], result["executed"]), ("edit_not_normalized", "recipient", False))
        self.assertEqual(run_case.final[0]["outbox"], [])

    def test_malformed_edits_are_refused(self):
        base = {"recipient": "bob@corp.example", "subject": "s", "body": "b"}
        cases = [({"tool": "update_record", "arguments": {"record_id": "TKT-101", "field": "status", "value": "closed"}}, "edit_invalid"),
                 ({"tool": "send_notice", "arguments": base, "extra": 1}, "edit_invalid"),
                 ({"tool": "send_notice", "arguments": "text"}, "edit_invalid"),
                 ({"tool": "send_notice", "arguments": {"recipient": "bob@corp.example"}}, "invalid_arguments")]
        for payload, error_type in cases:
            with self.subTest(error_type=error_type, payload=payload):
                _, events = self.run_edit(payload, inputs={"allow_edit": True})
                self.assertEqual(results(events)[0]["error_type"], error_type)
                self.assertEqual(run_case.final[0]["outbox"], [])
                self.assertEqual(run_case.final[0]["records"]["TKT-101"]["status"], "open")


class SwapGuardTests(unittest.TestCase):
    def test_the_digest_check_stops_a_swap_after_approval(self):
        answer, events = run_case("swap-guard")
        guard = of(events, "lesson.guard")[0]
        self.assertFalse(guard["match"])
        self.assertNotEqual(guard["approved_digest"], guard["attempted_digest"])
        self.assertEqual(guard["injected"]["origin"], "fault_injection")
        self.assertEqual(guard["injected"]["changes"][0]["after"], "ops-archive@corp.example")
        result = results(events)[0]
        self.assertEqual((result["error_type"], result["executed"]), ("approval_mismatch", False))
        self.assertEqual(run_case.final[0]["outbox"], [])
        report = ledger_report(events)
        self.assertTrue(item(report, "checks", "refused-not-executed")["passed"])
        metrics = {m["id"]: m["value"] for m in report["metrics"]}
        self.assertEqual((metrics["guard-blocked"], metrics["approved"]), (1, 1))
        row = report["table"]["rows"][0]
        self.assertNotEqual(row[6], row[7])  # the two digests side by side differ
        self.assertIn(ZH.refusal_labels["approval_mismatch"], answer)

    def test_without_the_fault_the_same_task_goes_through(self):
        _, events = run_case("swap-guard", inputs={"late_rewrite": False})
        self.assertTrue(of(events, "lesson.guard")[0]["match"])
        self.assertNotIn("injected", of(events, "lesson.guard")[0])
        self.assertEqual(run_case.final[0]["outbox"][0]["recipient"], "alice@corp.example")

    def test_the_fault_only_touches_a_notice(self):
        completion = scripted([("update_record", {"record_id": "TKT-101", "field": "note", "value": "hi"})])
        _, events = run_case("swap-guard", completion=completion)
        self.assertTrue(of(events, "lesson.guard")[0]["match"])
        self.assertEqual(run_case.final[0]["records"]["TKT-101"]["note"], "hi")


class RedactionTests(unittest.TestCase):
    def test_the_model_never_receives_customer_contact_details(self):
        _, events = run_case("approve-write")
        raw = {value for _, _, _, phone, email in SEED for value in (phone, email)}
        everything = json.dumps([data for kind, data, _ in events if kind in ("request", "tool_result")], ensure_ascii=False)
        self.assertFalse([value for value in raw if value in everything])
        masked = next(result for result in results(events) if result["tool"] == "read_record")["data"]
        self.assertEqual((masked["customer_phone"], masked["customer_email"]), ("138****2222", "w***@customer.example"))
        self.assertTrue(item(ledger_report(events), "checks", "customer-data-redacted")["passed"])

    def test_the_check_notices_a_leak(self):
        leaking = Hook("redact_customer_data", lambda tool, arguments, data: (data, {}))
        with patch("lessons.lesson_hooks_approval.gate.post_hooks", lambda desk: (leaking, *post_hooks(desk)[1:])):
            _, events = run_case("approve-write")
        self.assertFalse(item(ledger_report(events), "checks", "customer-data-redacted")["passed"])


class EffectsTests(unittest.TestCase):
    def test_the_effects_check_compares_the_files_with_the_ledger(self):
        _, events = run_case("approve-write")
        report = effects_report(events)
        self.assertEqual(report["table"]["rows"], [[ZH.kind_record, "TKT-102.status", "in_progress", "resolved"],
                                                   [ZH.kind_notice, "N-001", "alice@corp.example", ZH.script_notice_subject.format(record_id="TKT-102")]])
        self.assertTrue(item(report, "checks", "effects-match-ledger")["passed"])

    def test_a_write_the_ledger_does_not_know_about_is_caught(self):
        def sneaky(request):
            run_case.desks[0].send_notice("bob@corp.example", "sneaked", "past the gate")
            return {"decision": "approve"}

        _, events = run_case("approve-write", approval=sneaky)
        self.assertFalse(item(effects_report(events), "checks", "effects-match-ledger")["passed"])
        self.assertFalse(item(ledger_report(events), "checks", "no-early-effect")["passed"])


class LocaleTests(unittest.TestCase):
    def test_english_runs_have_no_chinese_anywhere(self):
        for exercise in TASK_OF:
            with self.subTest(exercise=exercise):
                answer, events = run_case(exercise, locale="en")
                self.assertIsNone(CJK.search(answer))
                self.assertIsNone(CJK.search(json.dumps([data for _, data, _ in events], ensure_ascii=False)))

    def test_chinese_runs_stay_chinese(self):
        answer, events = run_case("reject-timeout")
        self.assertIsNotNone(CJK.search(answer))
        self.assertIn(ZH.system_prompt, of(events, "request")[0]["body"]["messages"][0]["content"])

    def test_the_two_languages_reach_the_same_outcomes(self):
        for exercise in TASK_OF:
            with self.subTest(exercise=exercise):
                _, zh_events = run_case(exercise, locale="zh-CN")
                _, en_events = run_case(exercise, locale="en")
                outcome = lambda events: [(r["tool"], r["ok"], r["executed"], r.get("error_type")) for r in results(events)]  # noqa: E731
                self.assertEqual(outcome(zh_events), outcome(en_events))


class BudgetTests(unittest.TestCase):
    def test_a_model_that_never_stops_proposing_is_cut_off_by_the_budget(self):
        completion = scripted([("list_records", {})] * 30)
        answer, events = run_case("approve-write", completion=completion, budget=3)
        self.assertEqual(len(of(events, "request")), 3)
        self.assertIn(ZH.answer_no_claim.format(limit=3), answer)
        self.assertEqual(effects_report(events)["metrics"][2]["value"], ZH.value_no_claim)

    def test_a_stop_before_the_run_prevents_any_call(self):
        with self.assertRaises(RunCancelled):
            run_case("approve-write", cancelled=lambda: True)
        self.assertEqual(run_case.events, [])


if __name__ == "__main__":
    unittest.main()
