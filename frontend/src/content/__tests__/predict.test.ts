import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { evaluatePredict } from "../predict";

const event = (
  type: string,
  data: Record<string, unknown> = {},
  provenance = "real_run",
): Trace =>
  ({
    type,
    round: 1,
    timestamp: "2026-10-02T00:00:00Z",
    data,
    provenance,
  }) as Trace;

const run = [
  event("request"),
  event("response"),
  event("tool_call", { id: "a", function: { name: "add_numbers" } }),
  event("tool_call", { id: "b", function: { name: "get_current_time" } }),
  event("tool_result", { tool_call_id: "a", name: "add_numbers" }),
  event("tool_result", { tool_call_id: "b", name: "get_current_time" }),
];

describe("evaluatePredict", () => {
  it("counts real events, optionally filtered by tool name", () => {
    expect(
      evaluatePredict(
        { kind: "count_events", event: "tool_call", name: null },
        run,
        2,
      ),
    ).toEqual({
      status: "computed",
      actual: 2,
      matches: true,
    });
    expect(
      evaluatePredict(
        { kind: "count_events", event: "tool_result", name: "add_numbers" },
        run,
        2,
      ),
    ).toEqual({ status: "computed", actual: 1, matches: false });
    expect(
      evaluatePredict(
        { kind: "count_events", event: "request", name: null },
        run,
      ),
    ).toEqual({
      status: "computed",
      actual: 1,
      matches: null,
    });
  });

  it("never computes from illustrations or recordings", () => {
    const shown = run.map((item) => ({
      ...item,
      provenance: "illustration" as const,
    }));
    expect(
      evaluatePredict(
        { kind: "count_events", event: "tool_call", name: null },
        shown,
        2,
      ),
    ).toEqual({
      status: "no-run",
    });
    const recorded = run.map((item) => ({
      ...item,
      provenance: "recorded_run" as const,
    }));
    expect(
      evaluatePredict(
        { kind: "count_events", event: "tool_call", name: null },
        recorded,
      ),
    ).toEqual({
      status: "no-run",
    });
    expect(
      evaluatePredict(
        { kind: "count_events", event: "tool_call", name: null },
        [],
      ),
    ).toEqual({
      status: "no-run",
    });
  });

  it("treats legacy v1 events without provenance as the learner's own run", () => {
    const legacy = run.map(
      ({ provenance: _ignored, ...rest }) => rest as Trace,
    );
    expect(
      evaluatePredict(
        { kind: "count_events", event: "tool_call", name: null },
        legacy,
        2,
      ),
    ).toMatchObject({
      matches: true,
    });
  });
});
