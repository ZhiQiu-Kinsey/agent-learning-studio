import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { deriveStage } from "../derive";
import both from "../__fixtures__/lesson-1-both.json";
import zero from "../__fixtures__/lesson-3-zero.json";

// Fixtures are deterministic-adapter runs that executed the real Python tools.
const run = both as Trace[];
const failing = zero as Trace[];
const node = (state: ReturnType<typeof deriveStage>, id: string) =>
  state.nodes.find((item) => item.id === id)!;

function deepFreeze<T>(value: T): T {
  if (value && typeof value === "object") {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

describe("deriveStage", () => {
  it("builds the whole topology up front and keeps every node dormant at the start", () => {
    const stage = deriveStage(run, 0);
    expect(stage.nodes.map((item) => item.id)).toEqual([
      "user",
      "runtime",
      "model",
      "tool:add_numbers",
      "tool:get_current_time",
    ]);
    expect(stage.nodes.every((item) => item.state === "dormant")).toBe(true);
    expect(stage.status).toBe("idle");
    expect(stage.signal).toBeNull();
    expect(stage.provenance).toBe("real_run");
    expect(deriveStage([], 0).nodes).toEqual([]);
  });

  it("shows a waiting model while a request has no response yet", () => {
    const stage = deriveStage(run, 2);
    expect(node(stage, "model").state).toBe("waiting");
    expect(stage.signal).toEqual({ edge: "runtime->model", eventIndex: 1 });
    expect(stage.spans).toMatchObject([
      { kind: "llm", status: "open", durationMs: null },
    ]);
    expect(stage.status).toBe("running");
  });

  it("activates a tool between its call and result and times spans from server timestamps", () => {
    expect(node(deriveStage(run, 4), "tool:add_numbers").state).toBe("active");
    const stage = deriveStage(run, 5);
    const tool = stage.spans.find((span) => span.kind === "tool")!;
    expect(tool).toMatchObject({
      name: "add_numbers",
      status: "closed",
      ok: true,
      endIndex: 4,
    });
    expect(tool.durationMs).toBe(
      Date.parse(run[4].timestamp) - Date.parse(run[3].timestamp),
    );
    expect(node(stage, "tool:add_numbers").state).toBe("idle");
    expect(node(stage, "tool:get_current_time").state).toBe("dormant");
  });

  it("fires exactly one signal per visible event that crosses an edge", () => {
    for (let cursor = 1; cursor <= run.length; cursor++) {
      const signal = deriveStage(run, cursor).signal;
      if (run[cursor - 1].type === "done") expect(signal).toBeNull();
      else expect(signal?.eventIndex).toBe(cursor - 1);
    }
  });

  it("reads the context film from what each request really sent", () => {
    const stage = deriveStage(run, run.length);
    expect(stage.status).toBe("completed");
    expect(stage.film).toHaveLength(2);
    expect(stage.film[0].messages.every((message) => !message.isNew)).toBe(
      true,
    );
    const second = stage.film[1].messages;
    expect(second.map((message) => message.role)).toEqual([
      "system",
      "user",
      "assistant",
      "tool",
      "tool",
    ]);
    expect(second.map((message) => message.isNew)).toEqual([
      false,
      false,
      true,
      true,
      true,
    ]);
    const reported = (run[8].data.body as { usage?: unknown }).usage ?? null;
    expect(stage.film[1].usage).toEqual(reported);
  });

  it("marks a tool that returned ok=false as an error without inventing a result", () => {
    const stage = deriveStage(failing, failing.length);
    expect(stage.spans.find((span) => span.kind === "tool")).toMatchObject({
      ok: false,
      status: "closed",
    });
    expect(
      node(
        stage,
        `tool:${stage.spans.find((span) => span.kind === "tool")!.name}`,
      ).state,
    ).toBe("error");
  });

  it("on stop marks only still-open tool calls as stopped and keeps finished results", () => {
    const stopped: Trace[] = [
      ...run.slice(0, 6), // second tool call has no result yet
      { ...run[10], data: { status: "cancelled" } },
    ];
    const stage = deriveStage(stopped, stopped.length);
    expect(stage.status).toBe("cancelled");
    const [first, second] = stage.spans.filter((span) => span.kind === "tool");
    expect(first).toMatchObject({ status: "closed", ok: true });
    expect(second).toMatchObject({ status: "stopped", endIndex: null });
    expect(node(stage, "tool:get_current_time").state).toBe("stopped");
  });

  it("pairs legacy v1 events without span ids by the shared span rules", () => {
    const legacy = run.map(({ type, round, timestamp, data }) => ({
      type,
      round,
      timestamp,
      data,
    })) as Trace[];
    const stage = deriveStage(legacy, legacy.length);
    expect(stage.spans.map((span) => [span.kind, span.status])).toEqual(
      deriveStage(run, run.length).spans.map((span) => [
        span.kind,
        span.status,
      ]),
    );
    expect(stage.provenance).toBe("unknown");
  });

  it("is pure: same input, same output, inputs untouched", () => {
    const frozen = deepFreeze(structuredClone(run));
    expect(deriveStage(frozen, 7)).toEqual(deriveStage(frozen, 7));
    expect(deriveStage(frozen, 99).cursor).toBe(frozen.length);
    expect(deriveStage(frozen, -3).cursor).toBe(0);
  });
});
