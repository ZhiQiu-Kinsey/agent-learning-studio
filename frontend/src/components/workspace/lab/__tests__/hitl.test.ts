import type { TFunction } from "i18next";
import { describe, expect, it } from "vitest";
import { deriveStage } from "../../../../stage/derive";
import { openApprovalSpan } from "../../../../stage/spans";
import { layoutTimeline } from "../../../../stage/timelineLayout";
import type { Trace } from "../../../../types";
import {
  approvalRecords,
  checkpointOf,
  pendingApproval,
  remainingMs,
  resumedFromOf,
} from "../approvals";
import { streamFacts, streamProgress } from "../streaming";
import { eventText } from "../useEventText";

const at = (ms: number) =>
  new Date(Date.UTC(2026, 9, 20, 0, 0, 0, ms)).toISOString();
let seq = 0;
const event = (
  type: string,
  data: Record<string, unknown>,
  ms: number,
  span: Partial<Trace> = {},
): Trace => ({
  type,
  round: 1,
  timestamp: at(ms),
  data,
  schema_version: 2,
  run_id: "r".repeat(32),
  seq: ++seq,
  ...span,
});

const chunk = (text: string) => ({
  object: "chat.completion.chunk",
  choices: [{ index: 0, delta: { content: text }, finish_reason: null }],
});

function streamRun(status: "completed" | "cancelled") {
  return [
    event("run_start", { locale: "en" }, 0, {
      span_id: "run-1",
      span_kind: "run",
    }),
    event("request", { stream: true, body: { stream: true } }, 10, {
      span_id: "llm-1",
      span_kind: "llm",
    }),
    event(
      "response_delta",
      {
        chunks: [chunk("Hel")],
        chunk_range: [1, 1],
        text: "Hel",
        received_ms: [120, 120],
      },
      130,
      { span_id: "llm-1", span_kind: "llm" },
    ),
    event(
      "response_delta",
      {
        chunks: [chunk("lo"), chunk(" wor")],
        chunk_range: [2, 3],
        text: "lo wor",
        received_ms: [200, 260],
      },
      400,
      { span_id: "llm-1", span_kind: "llm" },
    ),
    event(
      "response",
      {
        body: {
          choices: [
            { index: 0, message: { role: "assistant", content: "Hello wor" } },
          ],
        },
        stream: {
          assembled_from_chunks: true,
          status,
          chunk_count: 3,
          first_chunk_ms: 120,
          first_token_ms: 120,
          done_marker: null,
          ...(status === "cancelled"
            ? { cancel_reason: "user_stop", discarded_after_cancel: 1 }
            : {}),
        },
      },
      410,
      { span_id: "llm-1", span_kind: "llm" },
    ),
  ];
}

const fakeT = ((key: string, options?: Record<string, unknown>) => {
  const shown = Object.entries(options ?? {}).filter(
    ([name]) => name !== "defaultValue",
  );
  return shown.length
    ? `${key} ${JSON.stringify(Object.fromEntries(shown))}`
    : key;
}) as unknown as TFunction<"lab", "bench.event">;

describe("streamed responses", () => {
  it("joins the text that really arrived, up to the cursor", () => {
    const events = streamRun("completed");
    expect(streamProgress(events.slice(0, 2))).toMatchObject({
      text: "",
      chunks: 0,
      finished: false,
    });
    const partial = streamProgress(events.slice(0, 3))!;
    expect(partial).toMatchObject({
      text: "Hel",
      chunks: 1,
      firstChunkMs: 120,
      finished: false,
    });
    const done = streamProgress(events)!;
    expect(done).toMatchObject({
      text: "Hello wor",
      chunks: 3,
      deltas: 2,
      finished: true,
    });
    expect(done.facts?.status).toBe("completed");
  });

  it("reads how a cancelled stream ended and ignores runs that did not stream", () => {
    const facts = streamFacts(streamRun("cancelled").at(-1)!)!;
    expect(facts).toMatchObject({
      status: "cancelled",
      chunkCount: 3,
      cancelReason: "user_stop",
      discardedAfterCancel: 1,
    });
    expect(streamProgress([event("request", { body: {} }, 0)])).toBeNull();
    expect(streamFacts(event("response", { body: {} }, 0))).toBeNull();
  });

  it("keeps parallel branches apart", () => {
    const events = [
      event("request", { stream: true, branch: "a" }, 0),
      event(
        "response_delta",
        { branch: "b", text: "other", chunk_range: [1, 1] },
        1,
      ),
      event(
        "response_delta",
        { branch: "a", text: "mine", chunk_range: [1, 1] },
        2,
      ),
    ];
    expect(streamProgress(events)!.text).toBe("mine");
  });

  it("stream chunks stay inside the request's llm span and fire real signals", () => {
    const stage = deriveStage(streamRun("completed"), 5);
    expect(stage.spans.filter((span) => span.kind === "llm")).toHaveLength(1);
    expect(stage.spans[0]).toMatchObject({
      status: "closed",
      startIndex: 1,
      endIndex: 4,
    });
    expect(deriveStage(streamRun("completed"), 3).signal?.edge).toBe(
      "model->runtime",
    );
  });

  it("has readable labels and summaries", () => {
    const { label, summary } = eventText(fakeT);
    const [, request, first, , response] = streamRun("cancelled");
    expect(label(request)).toBe("streamRequest");
    expect(label(first)).toBe("name.response_delta");
    expect(summary(first)).toBe('deltaSummary {"from":1,"to":1,"chars":3}');
    expect(label(response)).toBe("streamResponse");
    expect(summary(response)).toBe(
      'streamResponseSummary {"chunks":3,"status":"streamStatus.cancelled"}',
    );
    const done = event(
      "done",
      { status: "cancelled", cancel_reason: "page_closed" },
      9,
    );
    expect(summary(done)).toBe(
      'doneCancelled {"reason":"cancelReason.page_closed"}',
    );
  });
});

const payload = { path: "notes/plan.md", content: "draft" };
const digest = `sha256:${"a".repeat(64)}`;

function approvalRun(resolved: Record<string, unknown> | null) {
  const events = [
    event("run_start", {}, 0, { span_id: "run-1", span_kind: "run" }),
    event(
      "approval_requested",
      {
        approval_id: "approval-1",
        kind: "file.write",
        summary: "write notes/plan.md",
        payload,
        payload_digest: digest,
        editable: true,
        timeout_s: 60,
        expires_at: at(60_000),
        risk: "high",
      },
      100,
      { span_id: "approval-1", span_kind: "approval" },
    ),
  ];
  if (resolved)
    events.push(
      event(
        "approval_resolved",
        {
          approval_id: "approval-1",
          payload_digest: digest,
          edited: false,
          waited_ms: 900,
          ...resolved,
        },
        1000,
        { span_id: "approval-1", span_kind: "approval" },
      ),
    );
  return events;
}

describe("approval gates", () => {
  it("pairs requests with their results by approval_id", () => {
    const pending = approvalRun(null);
    expect(pendingApproval(pending)?.request).toMatchObject({
      approvalId: "approval-1",
      kind: "file.write",
      payload,
      payloadDigest: digest,
      editable: true,
      risk: "high",
    });
    const done = approvalRun({
      outcome: "rejected",
      decided_by: "learner",
      note: "no",
    });
    expect(pendingApproval(done)).toBeNull();
    const [record] = approvalRecords(done);
    expect(record.resolution).toMatchObject({
      outcome: "rejected",
      decidedBy: "learner",
      note: "no",
      waitedMs: 900,
    });
    expect(record.resolvedIndex).toBe(2);
  });

  it("a replay before the decision shows the request as still open", () => {
    const done = approvalRun({ outcome: "approved", decided_by: "learner" });
    expect(pendingApproval(done.slice(0, 2))).not.toBeNull();
  });

  it("counts down only from the server's deadline", () => {
    expect(remainingMs(at(60_000), Date.parse(at(59_000)))).toBe(1000);
    expect(remainingMs(at(60_000), Date.parse(at(61_000)))).toBe(0);
    expect(remainingMs(null, 0)).toBeNull();
    expect(remainingMs("not a date", 0)).toBeNull();
  });

  it("the paused interval is an approval span on the timeline", () => {
    const pending = deriveStage(approvalRun(null), 2);
    expect(openApprovalSpan(pending.spans)).toMatchObject({
      kind: "approval",
      status: "open",
    });
    const done = approvalRun({ outcome: "approved", decided_by: "learner" });
    const stage = deriveStage(done, 3);
    expect(stage.spans).toEqual([
      expect.objectContaining({
        kind: "approval",
        status: "closed",
        ok: true,
        durationMs: 900,
      }),
    ]);
    const { lanes } = layoutTimeline(done, stage.spans, "time");
    expect(lanes.map((lane) => lane.kind)).toEqual(["approval"]);
    // A run stopped while waiting leaves the gate open; the stage marks it stopped.
    const stopped = [
      ...approvalRun(null),
      event("done", { status: "cancelled" }, 2000),
    ];
    expect(deriveStage(stopped, 3).spans[0].status).toBe("stopped");
  });

  it("labels approvals and checkpoints from their data", () => {
    const { label, summary } = eventText(fakeT);
    const [, requested, resolved] = approvalRun({
      outcome: "timeout",
      decided_by: "timeout",
    });
    expect(label(requested)).toBe("name.approval_requested");
    expect(summary(requested)).toBe("write notes/plan.md");
    expect(summary(resolved)).toBe(
      'approvalResolvedSummary {"outcome":"approvalOutcome.timeout","by":"approvalBy.timeout"}',
    );
    const checkpoint = event(
      "checkpoint",
      { checkpoint_id: "cp-2", name: "before-save", state: {} },
      5,
    );
    expect(label(checkpoint)).toBe("name.checkpoint");
    expect(summary(checkpoint)).toBe(
      'checkpointSummary {"name":"before-save","id":"cp-2"}',
    );
    expect(checkpointOf(checkpoint)).toEqual({
      id: "cp-2",
      name: "before-save",
    });
    expect(checkpointOf(requested)).toBeNull();
  });

  it("reads where a resumed run started", () => {
    const start = event(
      "run_start",
      {
        resumed_from: {
          run_id: "s".repeat(32),
          checkpoint_id: "cp-1",
          name: "before-save",
        },
      },
      0,
    );
    expect(resumedFromOf([start])).toEqual({
      runId: "s".repeat(32),
      checkpointId: "cp-1",
      name: "before-save",
    });
    expect(resumedFromOf([event("run_start", {}, 0)])).toBeNull();
  });
});
