"""The remote agent of a2a-delegation: a Bluestone Library reference checker behind an A2A interface.

The runner starts it as ``python -m lessons.lesson_a2a_delegation.worker --locale en --fault none``:
a separate process that binds 127.0.0.1 on a free port, prints ``PORT <n>`` and then serves its
Agent Card and the JSON-RPC binding of A2A (a2a-sdk 1.x, protocol 1.0).

It is a deterministic program on purpose. A process of its own cannot use the parent's RunContext,
so a model call made here would never be recorded, and it would need the API key passed to a child.
A2A does not care: the protocol only sees the card, the task states and the artifact.
"""
import argparse
import asyncio
import socket

import uvicorn
from a2a.helpers import get_data_parts, new_data_part, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from starlette.applications import Starlette

from course.i18n import RUNTIME_LOCALES, SOURCE_LOCALE
from lessons.lesson_a2a_delegation.locales.worker import Texts, texts_for
from lessons.lesson_document_loading.chunking import Chunk, default_chunks
from lessons.lesson_keyword_retrieval.bm25 import BM25Index

AGENT_NAME = "bluestone-reference-checker"
SKILL_ID = "find-evidence"
# Fault injection for the failure exercises; the runner passes it on the command line and records it.
FAULTS = ("none", "slow", "fail", "partial")
MAX_CLAIMS = 3
TOP_K = 2
MAX_EVIDENCE = 3
STEP_SECONDS = 0.3   # each claim takes a moment, so the WORKING updates are spread out
SLOW_SECONDS = 60    # "slow" waits this long for an index rebuild before it starts


def section(anchor: str) -> str:
    return anchor.split("#", 1)[1]


class Handbook:
    """The handbook of the retrieval lessons, searched with BM25; versions come from front matter."""

    def __init__(self, locale: str):
        self.chunks = default_chunks(locale)
        self.by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        self.index = BM25Index(self.chunks, locale)
        # supersedes: hours replaces hours-2025, so an hours-2025 passage must not stand alone.
        self.replaced_by = {old: chunk.doc_id for chunk in self.chunks for old in chunk.supersedes}

    def check(self, t: Texts, claim: dict) -> dict:
        evidence, superseded = [], []
        for hit in self.index.search(claim["text"], TOP_K):
            chunk = self.by_id[hit.chunk_id]
            current = self.replaced_by.get(chunk.doc_id)
            if current is None:
                evidence.append(chunk)
                continue
            # The checker's rule: swap an old version for the current chunks of the same sections.
            sections = {section(anchor) for anchor in chunk.anchors}
            evidence += [c for c in self.chunks if c.doc_id == current and sections & {section(a) for a in c.anchors}]
            superseded.append({"chunk_id": chunk.chunk_id, "version": chunk.version, "replaced_by": current,
                               "note": t.superseded_note.format(old=chunk.doc_id, new=current)})
        unique = list({chunk.chunk_id: chunk for chunk in evidence}.values())[:MAX_EVIDENCE]
        return {"claim_id": claim["id"], "claim": claim["text"],
                "evidence": [passage(chunk) for chunk in unique], "superseded": superseded}


def passage(chunk: Chunk) -> dict:
    # Strings only: a protobuf Struct would turn every number into a float.
    return {"chunk_id": chunk.chunk_id, "title": chunk.title, "version": chunk.version,
            "anchors": list(chunk.anchors), "text": chunk.text}


def read_claims(context: RequestContext) -> list[dict] | None:
    """The input contract of the skill: metadata.skill_id, then a data part with 1 to 3 claims {id, text}."""
    message = context.message
    if message.metadata.fields.get("skill_id") is None or message.metadata["skill_id"] != SKILL_ID:
        return None
    for data in get_data_parts(message.parts):
        claims = data.get("claims") if isinstance(data, dict) else None
        if (isinstance(claims, list) and 1 <= len(claims) <= MAX_CLAIMS
                and all(isinstance(c, dict) and isinstance(c.get("id"), str) and isinstance(c.get("text"), str)
                        and c["text"].strip() for c in claims)):
            return claims
    return None


class ReferenceChecker(AgentExecutor):
    def __init__(self, t: Texts, handbook: Handbook, fault: str):
        self.t, self.handbook, self.fault = t, handbook, fault

    def say(self, text: str, task) -> object:
        return new_text_message(text, context_id=task.context_id, task_id=task.id)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        t = self.t
        # 1. Accept: the first event is the Task itself, in SUBMITTED.
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        claims = read_claims(context)
        if claims is None:
            await updater.update_status(TaskState.TASK_STATE_REJECTED, message=self.say(t.status_rejected, task))
            return
        # 2. Work: WORKING, with a status message the delegator can show while it waits.
        await updater.update_status(TaskState.TASK_STATE_WORKING, message=self.say(
            t.status_received.format(count=len(claims), chunks=len(self.handbook.chunks)), task))
        if self.fault == "slow":
            for second in range(1, SLOW_SECONDS + 1):
                await asyncio.sleep(1)
                await updater.update_status(TaskState.TASK_STATE_WORKING,
                                            message=self.say(t.status_waiting_index.format(seconds=second), task))
        if self.fault == "fail":
            await updater.update_status(TaskState.TASK_STATE_FAILED, message=self.say(t.status_failed, task))
            return
        # "partial" drops every claim after the first and still reports COMPLETED: a remote bug, not a protocol error.
        results = []
        for claim in claims[:1] if self.fault == "partial" else claims:
            await asyncio.sleep(STEP_SECONDS)
            results.append(self.handbook.check(t, claim))
            await updater.update_status(TaskState.TASK_STATE_WORKING, message=self.say(
                t.status_checked.format(claim_id=claim["id"], evidence=len(results[-1]["evidence"])), task))
        # 3. Deliver: one artifact (data for the program, text for people), then the terminal state.
        await updater.add_artifact(parts=[new_data_part({"results": results}),
                                          new_text_part(t.artifact_summary.format(count=len(results)))],
                                   name="evidence-report", last_chunk=True)
        await updater.update_status(TaskState.TASK_STATE_COMPLETED, message=self.say(t.status_done, task))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # The SDK also cancels the running execute(); this only records why the task ended.
        updater = TaskUpdater(event_queue=event_queue, task_id=context.task_id, context_id=context.context_id)
        await updater.update_status(TaskState.TASK_STATE_CANCELED, message=new_text_message(
            self.t.status_canceled, context_id=context.context_id, task_id=context.task_id))


def agent_card(t: Texts, url: str) -> AgentCard:
    return AgentCard(
        name=AGENT_NAME, description=t.agent_description, version="1.0.0",
        default_input_modes=["application/json"], default_output_modes=["application/json", "text/plain"],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=url, protocol_version="1.0")],
        skills=[AgentSkill(id=SKILL_ID, name=t.skill_name, description=t.skill_description, tags=["handbook"],
                           examples=list(t.skill_examples), input_modes=["application/json"],
                           output_modes=["application/json", "text/plain"])],
    )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Bluestone reference checker over A2A (JSON-RPC).")
    parser.add_argument("--locale", choices=RUNTIME_LOCALES, default=SOURCE_LOCALE)
    parser.add_argument("--fault", choices=FAULTS, default="none")
    args = parser.parse_args(argv)
    t = texts_for(args.locale)
    # Bind and listen first, then announce: a connection that arrives before uvicorn has started waits in
    # the backlog instead of being refused.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(64)
    port = sock.getsockname()[1]
    card = agent_card(t, f"http://127.0.0.1:{port}")
    handler = DefaultRequestHandler(agent_executor=ReferenceChecker(t, Handbook(args.locale), args.fault),
                                    task_store=InMemoryTaskStore(), agent_card=card)
    app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")])
    print(f"PORT {port}", flush=True)
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])


if __name__ == "__main__":
    main()
