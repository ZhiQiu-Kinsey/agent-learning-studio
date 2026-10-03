import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { findEvidence, resolvePath, selectEvents } from "../selector";
import both from "../../stage/__fixtures__/lesson-1-both.json";
import zero from "../../stage/__fixtures__/lesson-3-zero.json";

const run = both as Trace[];
const none = {
  event: null,
  round: null,
  path: null,
  span_kind: null,
  name: null,
  nth: null,
};

describe("resolvePath", () => {
  it("walks objects and arrays and never invents values", () => {
    const value = { data: { list: [{ a: 1 }, { a: 0 }] } };
    expect(resolvePath(value, "data.list[1].a")).toBe(0);
    expect(resolvePath(value, "data.list[2].a")).toBeUndefined();
    expect(resolvePath(value, "data.list.a")).toBeUndefined();
    expect(resolvePath(value, "data.missing")).toBeUndefined();
    expect(resolvePath({ a: null }, "a")).toBeNull();
    expect(resolvePath({}, "constructor")).toBeUndefined();
  });
});

describe("selectors", () => {
  it("match by event type, round, span kind, tool name and JSON path", () => {
    expect(selectEvents({ ...none, event: "tool_call" }, run)).toEqual([3, 5]);
    expect(
      selectEvents(
        { ...none, event: "tool_call", name: "get_current_time" },
        run,
      ),
    ).toEqual([5]);
    expect(selectEvents({ ...none, event: "request", round: 2 }, run)).toEqual([
      7,
    ]);
    expect(selectEvents({ ...none, span_kind: "llm" }, run)).toEqual([
      1, 2, 7, 8,
    ]);
    expect(
      selectEvents(
        {
          ...none,
          event: "request",
          path: "data.body.messages[3].tool_call_id",
        },
        run,
      ),
    ).toEqual([7]);
  });

  it("finds evidence with its value, or says the run did not produce it", () => {
    const result = findEvidence(
      {
        ...none,
        event: "tool_result",
        name: "add_numbers",
        path: "data.result.result",
      },
      run,
    );
    expect(result).toEqual({ found: true, index: 4, value: 42 });
    expect(findEvidence({ ...none, event: "tool_call" }, run, 4)).toMatchObject(
      { index: 5 },
    );
    expect(
      findEvidence(
        { ...none, event: "tool_call", name: "add_numbers" },
        zero as Trace[],
      ),
    ).toEqual({
      found: false,
    });
  });
});
