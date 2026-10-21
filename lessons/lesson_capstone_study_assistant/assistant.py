"""The study assistant: one tool loop, a permission gate in front of every tool, and one function per kind of task.

Nothing in this file is a new mechanism. The loop is the native tool loop of the first
lessons; retrieval is the notes search of the retrieval lessons; the progress store is the
persistent-memory store; approvals and checkpoints are the platform's. What the capstone
adds is the order they run in and where each one is enforced:

1. the contract picks the task's permissions before the model is called;
2. the model proposes calls, and the gate (gate.py) judges each one before anything runs;
3. a write waits for a person, then runs once under an operation id;
4. a verifier (verifier.py) reads only the recorded facts and decides the case.
"""
import json
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from course.execution import RunContext
from lessons.lesson_capstone_study_assistant import answers, gate
from lessons.lesson_capstone_study_assistant.contract import KIND_TASK, LEARNER, MAX_STEPS, READ, WRITE, Case
from lessons.lesson_capstone_study_assistant.ledger import Ledger, model_view, trace_truth
from lessons.lesson_capstone_study_assistant.locales import Texts
from lessons.lesson_capstone_study_assistant.progress import ProgressStore, operation_id

TOOL_NAMES = ("search_notes", "read_progress", "save_progress")
# What each tool really does, written here and not taken from the gate's decision: the verifier compares the two.
TOOL_MODES = {"search_notes": READ, "read_progress": READ, "save_progress": WRITE}
SAVE_KIND = "progress.save"
STAGES = ("contract", "tools", "answer", "approval", "verify")


class SimulatedCrash(RuntimeError):
    """Fault injection: the process 'dies' after the approval and before the write. Not a model or tool failure."""


@dataclass
class Env:
    """What one run shares across its cases: the platform context, the notes search, the ledger and the round counter."""
    context: RunContext
    t: Texts
    backend: object  # anything with search(query, top_k) -> {"hits": [...]}
    chunks: dict  # chunk_id -> Chunk of this language
    ledger: Ledger
    top_k: int = 5
    rounds: int = 0

    @property
    def locale(self) -> str:
        return self.context.locale

    def next_round(self) -> int:
        self.rounds += 1
        return self.rounds


class Plan:
    """The stages of one case as lesson.plan versions: the runner moves them, the model never does."""

    def __init__(self, env: Env, case_id: str, stages: tuple[str, ...]):
        self.env, self.case_id, self.stages = env, case_id, stages
        self.status = {stage: "pending" for stage in stages}
        self.version = 0

    def set(self, stage: str, status: str, reason: str = "") -> None:
        if stage in self.status:
            self.status[stage] = status
            self.version += 1
            self.env.context.emit("lesson.plan", {
                "version": self.version, "event": "stage", "case": self.case_id, "reason": reason,
                "steps": [{"id": name, "content": self.env.t.stage_names[name], "status": self.status[name]}
                          for name in self.stages]}, max(self.env.rounds, 1))


@contextmanager
def case_store(env: Env, persistent: Path | None = None):
    """The progress file of one case: the learner's real file when asked, otherwise a throwaway directory."""
    if persistent is not None:
        persistent.parent.mkdir(parents=True, exist_ok=True)
        yield persistent
        return
    with tempfile.TemporaryDirectory(prefix="study-assistant-") as directory:
        yield Path(directory) / "progress.sqlite3"


class Session:
    """One conversation: its task (hence its permissions), its learner, its store and the record of what happened."""

    def __init__(self, env: Env, case: Case, task: str, path: Path, *, fault: str | None = None,
                 origin: str = "model"):
        self.env, self.case, self.task, self.learner = env, case, task, LEARNER
        self.store = ProgressStore(path, env.locale)
        self.provided: dict = {}  # chunk_id -> Chunk, in the order the searches returned them
        self.decisions: list[dict] = []
        self.executions: list[dict] = []  # effects that really happened, written where they happen
        self.approvals: list[dict] = []
        self.fault, self.origin = fault, origin
        self.checkpoint_state: dict | None = None  # the state saved just before the approval wait
        # One registry per session: every proposal of a conversation goes through the same guarded functions.
        self.tools = self.registry()

    def close(self) -> None:
        self.store.close()

    # ---------- the tool registry: every name is registered, the gate decides per task ----------

    def registry(self) -> dict:
        return {name: self._guarded(name) for name in TOOL_NAMES}

    def _guarded(self, name: str):
        def guarded(**arguments):
            return self.call(name, arguments)
        return guarded

    def call(self, name: str, arguments: dict):
        t, context = self.env.t, self.env.context
        # 1. The gate decides from the contract, the bound identity and the arguments; nothing else.
        decision = gate.decide(self.task, self.learner, name, arguments)
        record = {"tool": name, "origin": self.origin, "task": self.task, "case": self.case.id,
                  "verdict": decision.verdict, "rule": decision.rule, "mode": decision.mode,
                  "message": t.gate_rules[decision.rule],
                  "arguments": {key: (value[:80] if isinstance(value, str) else value) for key, value in arguments.items()}}
        self.decisions.append(record)
        context.emit("lesson.permission", record, max(self.env.rounds, 1))
        decision.raise_for(t.gate_rules)
        # 2. Allowed: a write goes through a person first; a read runs at once.
        if gate.needs_approval(self.task, name):
            return self._approved_write(arguments)
        started = time.perf_counter()
        try:
            result = self._read(name, arguments)
        except Exception:
            self.env.ledger.add(self.case.id, "tool", name, started, status="error", origin=self.origin)
            raise
        self.executions.append({"tool": name, "mode": TOOL_MODES[name], "ok": True})
        self.env.ledger.add(self.case.id, "tool", name, started, status="ok", origin=self.origin,
                            hits=len(result["hits"]) if name == "search_notes" else None)
        return result

    def _read(self, name: str, arguments: dict) -> dict:
        if name == "search_notes":
            result = self.env.backend.search(arguments["query"], arguments.get("top_k", self.env.top_k))
            for hit in result["hits"]:
                self.provided.setdefault(hit["chunk_id"], self.env.chunks[hit["chunk_id"]])
            return result
        if name != "read_progress":
            raise ValueError(f"{name} is not a read tool")
        records = self.store.records(self.learner)
        self.env.context.emit("lesson.memory", {"action": "recalled", "namespace": self.learner,
                                                 "included": [row["lesson"] for row in records],
                                                 "storage": self.env_storage()}, max(self.env.rounds, 1))
        return {"learner": self.learner, "records": records}

    def env_storage(self) -> str:
        return "temporary" if self.env.context.mode == "offline" else "local-persistent"

    # ---------- the write path: checkpoint, approval, re-check, idempotent apply ----------

    def payload_for(self, arguments: dict) -> dict:
        return {"learner": arguments["learner"], "lesson": arguments["lesson"], "status": arguments["status"],
                "note": arguments["note"],
                "operation_id": operation_id(arguments["learner"], arguments["lesson"], arguments["status"],
                                             arguments["note"])}

    def _approved_write(self, arguments: dict):
        context = self.env.context
        payload = self.payload_for(arguments)
        # 1. Save where the run stands before waiting, so a stopped or crashed run can continue from here.
        self.checkpoint_state = {"stage": "awaiting_approval", "case": self.case.id, "payload": payload}
        context.checkpoint("before-save", self.checkpoint_state, max(self.env.rounds, 1))
        return self.finish_write(payload)

    def finish_write(self, payload: dict):
        """Approval, re-check, apply. Shared by a live write and a resumed one, so both go through the same steps."""
        t, context = self.env.t, self.env.context
        # 2. Ask a person about exactly these arguments; the digest in the request is what they approve.
        decision = context.request_approval(
            SAVE_KIND, t.approval_summary.format(lesson=payload["lesson"], status=t.status_names[payload["status"]]),
            payload, risk="medium", round_number=max(self.env.rounds, 1))
        self.approvals.append({"outcome": decision.outcome, "decided_by": decision.decided_by,
                               "operation_id": payload["operation_id"], "waited_ms": decision.waited_ms})
        self.env.ledger.approval(self.case.id, SAVE_KIND, decision.waited_ms, decision.outcome)
        if not decision.approved:
            rule = "approval_timeout" if decision.outcome == "timeout" else "approval_rejected"
            raise gate.ApprovalRejected(rule, t.gate_rules[rule])
        # 3. Act only on what was approved, and check once more right before the effect.
        if not decision.matches(payload):
            raise gate.PermissionDenied("payload_changed", t.gate_rules["payload_changed"])
        if self.fault == "crash_after_approval":
            raise SimulatedCrash(t.crash_message)
        return self.apply(payload)

    def apply(self, payload: dict) -> dict:
        context = self.env.context
        started = time.perf_counter()
        result = self.store.apply(payload["operation_id"], payload["learner"], payload["lesson"], payload["status"],
                                  payload["note"])
        record = {"lesson": payload["lesson"], "status": payload["status"], "note": payload["note"],
                  "version": result["version"]}
        context.emit("lesson.memory", {"action": "saved" if result["applied"] else "replayed", "record": record,
                                        "operation_id": payload["operation_id"], "reason": result["reason"],
                                        "storage": self.env_storage()}, max(self.env.rounds, 1))
        context.checkpoint("after-save", {"stage": "saved", "case": self.case.id, "operation_id": payload["operation_id"]},
                           max(self.env.rounds, 1))
        self.executions.append({"tool": "save_progress", "mode": WRITE, "ok": True, "applied": result["applied"],
                                "reason": result["reason"], "operation_id": payload["operation_id"]})
        self.env.ledger.add(self.case.id, "tool", "save_progress", started, status="ok", origin=self.origin)
        return {"saved": True, **result}


# ---------- the tool loop ----------

def tool_definitions(t: Texts) -> list[dict]:
    """The three tools the model is offered in every task; names and argument names are code, descriptions are text."""
    def function(name: str, description: str, properties: dict, required: list[str]) -> dict:
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {
            "type": "object", "properties": properties, "required": required}}}
    return [
        function("search_notes", t.tool_search, {
            "query": {"type": "string", "description": t.param_query},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 8, "description": t.param_top_k}}, ["query"]),
        function("read_progress", t.tool_read, {"learner": {"type": "string", "description": t.param_learner}},
                 ["learner"]),
        function("save_progress", t.tool_save, {
            "learner": {"type": "string", "description": t.param_learner},
            "lesson": {"type": "string", "description": t.param_lesson},
            "status": {"type": "string", "enum": ["started", "done", "needs_review"], "description": t.param_status},
            "note": {"type": "string", "description": t.param_note}}, ["learner", "lesson", "status", "note"]),
    ]


def system_message(t: Texts, output_format: str) -> dict:
    return {"role": "system", "content": t.system_prompt.format(learner=LEARNER) + "\n" + output_format}


def converse(session: Session, messages: list[dict]) -> dict:
    """The tool loop. It stops on a final answer or after MAX_STEPS model calls; it never raises for running out."""
    env = session.env
    tools, called = tool_definitions(env.t), []
    for step in range(1, MAX_STEPS + 1):
        env.context.check_cancelled()
        # 1. Every step sends the whole history and the tool definitions, as in the first lessons.
        body = {"messages": messages, "tools": tools, "tool_choice": "auto", "temperature": 0}
        response = env.ledger.model_call(env.context, session.case.id, body, env.next_round())
        message = response["choices"][0]["message"]
        proposals = message.get("tool_calls") or []
        # 2. No proposals: the content is the final answer and the conversation ended.
        if not proposals:
            return {"content": message.get("content") or "", "ended": True, "steps": step, "called": called,
                    "fixture": response.get("x_offline_fixture")}
        messages.append(message)
        # 3. Each proposal runs through the platform allowlist and then our gate; the result goes back as data.
        for proposal in proposals:
            result = env.context.execute_proposal(proposal, session.tools)
            called.append({"name": proposal["function"]["name"], "arguments": proposal["function"].get("arguments"),
                           "ok": result["ok"], "error_type": result.get("error_type")})
            messages.append({"role": "tool", "tool_call_id": proposal["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return {"content": None, "ended": False, "steps": MAX_STEPS, "called": called, "fixture": None}


# ---------- one function per kind of task ----------

def source_of(env: Env) -> str:
    """Who wrote the answer: the model, or the offline fixture. The event says so; nothing is guessed from the text."""
    return "offline_fixture" if env.context.mode == "offline" else "model"


def _base(case: Case, session: Session, plan: Plan, mark: int, started: float, before: str) -> dict:
    return {"case": case, "ended": False, "steps": 0, "called": [], "content": None, "problems": [],
            "decisions": session.decisions, "executions": session.executions, "approvals": session.approvals,
            "store_before": before, "store_after": None, "rows": [], "e2e_ms": 0.0, "source": None,
            "plan": plan, "provided": [], "mark": mark, "started": started}


def _finish(env: Env, session: Session, outcome: dict) -> dict:
    outcome["store_after"] = session.store.digest()
    outcome["rows"] = env.ledger.since(outcome["mark"])
    outcome["e2e_ms"] = round((time.perf_counter() - outcome["started"]) * 1000, 1)
    outcome["provided"] = list(session.provided.values())
    return outcome


def run_grounded(env: Env, case: Case, path: Path, kind: str | None = None) -> dict:
    """Ask and injection cases (and the practice case): retrieval through the gate, then a grounded structured answer."""
    t = env.t
    kind = kind or case.kind
    task = KIND_TASK[kind]
    plan = Plan(env, case.id, ("contract", "tools", "answer", "verify"))
    plan.set("contract", "done", t.reason_contract.format(task=task))
    session = Session(env, case, task, path)
    try:
        # Seed one learner record so "the store did not change" means something for the injection cases.
        if kind == "injection":
            session.store.apply(operation_id(LEARNER, "tool-selection", "done", t.seed_note), LEARNER,
                                "tool-selection", "done", t.seed_note)
        mark, started, before = env.ledger.mark(), time.perf_counter(), session.store.digest()
        outcome = _base(case, session, plan, mark, started, before)
        output_format = {"ask": t.format_ask, "injection": t.format_ask, "practice": t.format_practice}[kind]
        messages = [system_message(t, output_format), {"role": "user", "content": t.case_questions[case.id]}]
        plan.set("tools", "in_progress")
        talk = converse(session, messages)
        outcome.update({key: talk[key] for key in ("ended", "steps", "called", "content")})
        outcome["source"] = source_of(env)
        plan.set("tools", "done" if talk["called"] else "skipped")
        plan.set("answer", "done" if talk["ended"] else "failed", t.reason_not_ended if not talk["ended"] else "")
        if talk["ended"]:
            parsed, problems = (answers.parse_model(talk["content"], answers.PracticeSet) if kind == "practice"
                                else answers.parse_answer(talk["content"]))
            outcome["answer"], outcome["problems"] = parsed, problems
        if kind == "injection":
            outcome["probes"] = run_probes(env, case, path)
        return _finish(env, session, outcome)
    finally:
        session.close()


def run_probes(env: Env, case: Case, path: Path) -> list[dict]:
    """Calls the injected post asks for, submitted by the runner itself (never by the model) to see the gate refuse them.

    They are labelled origin course_program in the events, so nobody mistakes them for something the model
    proposed. They exist because a model may well ignore the injection: then the model path proves nothing about the gate.
    """
    t, results = env.t, []
    for task, name, arguments, label in (
            ("ask", "save_progress", {"learner": LEARNER, "lesson": "rag-citations", "status": "done",
                                      "note": t.probe_note}, "write_in_read_only_task"),
            ("save", "save_progress", {"learner": "admin", "lesson": "rag-citations", "status": "done",
                                       "note": t.probe_note}, "other_learner_write"),
            ("recall", "read_progress", {"learner": "student_b"}, "other_learner_read"),
            ("ask", "delete_progress", {}, "unregistered_tool")):
        session = Session(env, case, task, path, origin="runner_probe")
        try:
            result = env.context.submit_call(name, json.dumps(arguments, ensure_ascii=False), session.tools,
                                             max(env.rounds, 1))
            decision = session.decisions[0] if session.decisions else None
            results.append({"probe": label, "task": task, "tool": name, "ok": result["ok"],
                            "error_type": result.get("error_type"), "rule": decision["rule"] if decision else None,
                            "layer": "gate" if decision else "platform_allowlist",
                            "executed": len(session.executions), "approvals": len(session.approvals)})
        finally:
            session.close()
    return results


def run_trace(env: Env, case: Case, path: Path) -> dict:
    """Ask a question, then ask the model to read this very ledger back: what was slowest, how many hits, usage?"""
    t = env.t
    outcome = run_grounded(env, case, path, kind="ask")
    rows = outcome["rows"]
    outcome["truth"] = trace_truth(rows)
    plan = Plan(env, case.id + "-trace", ("contract", "answer", "verify"))
    plan.set("contract", "done", t.reason_trace)
    messages = [system_message(t, t.format_trace),
                {"role": "user", "content": t.trace_prompt.format(question=t.case_questions[case.id],
                                                                   ledger=json.dumps(model_view(rows), ensure_ascii=False))}]
    response = env.ledger.model_call(env.context, case.id, {"messages": messages, "temperature": 0}, env.next_round())
    content = response["choices"][0]["message"].get("content") or ""
    outcome["explanation"], outcome["explain_problems"] = answers.parse_model(content, answers.TraceExplanation)
    plan.set("answer", "done")
    # The explanation call is a row of this case too; the truth above was computed before it, from the rows it explains.
    outcome["rows"] = env.ledger.since(outcome["mark"])
    outcome["e2e_ms"] = round((time.perf_counter() - outcome["started"]) * 1000, 1)
    return outcome


def progress_messages(env: Env, text: str) -> list[dict]:
    t = env.t
    return [system_message(t, t.format_progress), {"role": "user", "content": text}]


def run_progress(env: Env, case: Case, path: Path) -> dict:
    """Save and recall: the learner says what they finished, a person approves, and a later session reads it back."""
    t = env.t
    plan = Plan(env, case.id, ("contract", "tools", "approval", "answer", "verify"))
    plan.set("contract", "done", t.reason_contract.format(task="save"))
    fault = "crash_after_approval" if case.subkind == "recovery" else None
    session = Session(env, case, "save", path, fault=fault)
    try:
        mark, started, before = env.ledger.mark(), time.perf_counter(), session.store.digest()
        outcome = _base(case, session, plan, mark, started, before)
        outcome["crashed"] = False
        plan.set("tools", "in_progress")
        try:
            talk = converse(session, progress_messages(env, t.case_questions[case.id]))
        except SimulatedCrash as crash:
            outcome["crashed"] = True
            plan.set("approval", "failed", str(crash))
            outcome["called"] = []
            outcome.update(resume_after_crash(env, case, path, session))
            return _finish(env, session, outcome)
        outcome.update({key: talk[key] for key in ("ended", "steps", "called", "content")})
        outcome["source"] = source_of(env)
        plan.set("tools", "done")
        plan.set("approval", "done" if session.approvals else "skipped")
        plan.set("answer", "done" if talk["ended"] else "failed")
        if talk["ended"]:
            outcome["reply"], outcome["problems"] = answers.parse_model(talk["content"], answers.ProgressReply)
        if case.subkind == "roundtrip":
            outcome["recall"] = run_recall(env, case, path)
        return _finish(env, session, outcome)
    finally:
        session.close()


def run_recall(env: Env, case: Case, path: Path) -> dict:
    """A new conversation: no message history, a new connection to the same file. Only the store carries over."""
    t = env.t
    session = Session(env, case, "recall", path)
    try:
        before = session.store.digest()
        talk = converse(session, progress_messages(env, t.recall_question))
        reply, problems = (answers.parse_model(talk["content"], answers.ProgressReply) if talk["ended"] else (None, []))
        return {"ended": talk["ended"], "steps": talk["steps"], "called": talk["called"], "reply": reply,
                "problems": problems, "records": session.store.records(LEARNER), "writes": sum(
                    1 for item in session.executions if item["mode"] == WRITE),
                "unchanged": before == session.store.digest(), "decisions": session.decisions,
                "executions": session.executions}
    finally:
        session.close()


def resume_save(env: Env, case: Case, path: Path, state: dict, *, origin: str = "resume") -> dict:
    """Finish an interrupted approved write from a checkpoint's state, in a session built from nothing.

    The checkpoint says which operation was meant, not that it ran. So the store is asked first: when the
    operation id is already there, nothing is requested and nothing is written.
    """
    t = env.t
    payload = state["payload"]
    session = Session(env, case, "save", path, origin=origin)
    try:
        plan = Plan(env, case.id + "-resume", ("contract", "approval", "answer"))
        plan.set("contract", "done", t.reason_resume)
        done = session.store.memory.connection.execute("SELECT version FROM progress_ops WHERE op_id=?",
                                                       (payload["operation_id"],)).fetchone()
        if done is not None:
            plan.set("approval", "skipped", t.reason_already_done)
            return {"resumed": True, "applied": False, "reason": "replayed", "approvals": 0,
                    "operation_id": payload["operation_id"], "version": done[0],
                    "records": session.store.records(LEARNER), "executions": list(session.executions),
                    "approval_records": list(session.approvals)}
        plan.set("approval", "in_progress")
        try:
            result = session.finish_write(payload)
            plan.set("approval", "done")
            return {"resumed": True, "applied": result["applied"], "reason": result["reason"],
                    "approvals": len(session.approvals), "operation_id": payload["operation_id"],
                    "version": result["version"], "records": session.store.records(LEARNER),
                    "executions": list(session.executions), "approval_records": list(session.approvals)}
        except gate.ApprovalRejected as error:
            plan.set("approval", "failed", str(error))
            return {"resumed": True, "applied": False, "reason": error.rule, "approvals": len(session.approvals),
                    "operation_id": payload["operation_id"], "version": None,
                    "records": session.store.records(LEARNER), "executions": list(session.executions),
                    "approval_records": list(session.approvals)}
    finally:
        session.close()


def resume_after_crash(env: Env, case: Case, path: Path, crashed: Session) -> dict:
    """The recovery case: drop every in-memory object, rebuild from the checkpoint, resume twice, count the writes.

    This is fault injection inside one process, labelled as such; the platform's own restart-and-resume path
    is the same resume_save, started from the stored checkpoint.
    """
    state = crashed.checkpoint_state
    first = resume_save(env, case, path, state)
    second = resume_save(env, case, path, state)
    # The writes of the resumed sessions are real executions of this case too: the permission check must see them.
    executions = list(crashed.executions) + first["executions"] + second["executions"]
    approvals = list(crashed.approvals) + first["approval_records"] + second["approval_records"]
    return {"resume_first": first, "resume_second": second, "state": state, "ended": True,
            "executions": executions, "approvals": approvals}
