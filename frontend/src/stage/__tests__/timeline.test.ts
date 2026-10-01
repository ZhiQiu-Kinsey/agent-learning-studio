import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { deriveStage } from "../derive";
import { layoutTimeline } from "../timelineLayout";
import both from "../__fixtures__/lesson-1-both.json";

const run = both as Trace[];
const spans = deriveStage(run, run.length).spans;

describe("layoutTimeline", () => {
  it("places bars by real server time and reports the real total", () => {
    const { lanes, totalMs, ticks } = layoutTimeline(run, spans, "time");
    expect(lanes.map((lane) => lane.id)).toEqual([
      "llm",
      "tool:add_numbers",
      "tool:get_current_time",
    ]);
    expect(totalMs).toBe(
      Date.parse(run.at(-1)!.timestamp) - Date.parse(run[0].timestamp),
    );
    expect(ticks[0]).toBe(0);
    expect(ticks.at(-1)).toBe(100);
  });

  it("spaces events evenly in uniform mode", () => {
    const { ticks, totalMs } = layoutTimeline(run, spans, "uniform");
    expect(totalMs).toBeNull();
    expect(ticks[5]).toBeCloseTo((5 / (run.length - 1)) * 100);
  });

  it("falls back to uniform spacing when a timestamp is unreadable", () => {
    const broken = run.map((event, index) =>
      index === 3 ? { ...event, timestamp: "?" } : event,
    );
    const result = layoutTimeline(broken, spans, "time");
    expect(result.fellBack).toBe(true);
    expect(result.totalMs).toBeNull();
  });
});
