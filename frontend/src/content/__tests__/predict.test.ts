import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { evaluatePredict, predictArm, predictEvents } from "../predict";
import type { Experiment } from "../types.gen";

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

  it("checks only a run of the predicted arm's exercise", () => {
    // multi-turn-history: the question is about "without-history"; a run of
    // "with-history" on screen must not be called a match or a mismatch.
    const experiments = [
      {
        id: "history-or-not",
        arms: [
          { id: "with-history", exercise: "with-history" },
          { id: "without-history", exercise: "without-history" },
        ],
      },
      { id: "growing", arms: [{ id: "three", exercise: "three-turns" }] },
    ] as unknown as Experiment[];
    const rule = {
      kind: "count_events",
      event: "request",
      name: null,
    } as const;
    const arm = predictArm(
      { experiment: "history-or-not", arm: "without-history" },
      experiments,
    );
    expect(arm?.exercise).toBe("without-history");
    expect(
      evaluatePredict(
        rule,
        predictEvents(arm?.exercise, "with-history", run),
        1,
      ),
    ).toEqual({ status: "no-run" });
    expect(
      evaluatePredict(rule, predictEvents(arm?.exercise, "", run), 1),
    ).toEqual({ status: "no-run" });
    expect(
      evaluatePredict(
        rule,
        predictEvents(arm?.exercise, "without-history", run),
        1,
      ),
    ).toEqual({ status: "computed", actual: 1, matches: true });
    // A single-arm experiment needs no arm; an unknown arm or experiment binds nothing.
    expect(
      predictArm({ experiment: "growing", arm: null }, experiments)?.exercise,
    ).toBe("three-turns");
    expect(
      predictArm({ experiment: "history-or-not", arm: null }, experiments),
    ).toBeNull();
    expect(
      predictArm({ experiment: "history-or-not", arm: "nope" }, experiments),
    ).toBeNull();
    expect(
      predictArm({ experiment: "nope", arm: null }, experiments),
    ).toBeNull();
    expect(predictEvents(null, "with-history", run)).toEqual([]);
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
