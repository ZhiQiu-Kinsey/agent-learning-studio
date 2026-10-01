import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { parseArguments, summarize } from "../ToolCards";
import both from "../__fixtures__/lesson-1-both.json";

const run = both as Trace[];

describe("tool card data", () => {
  it("summarizes only what the events contain", () => {
    expect(summarize(run[3], run[4])).toEqual({
      name: "add_numbers",
      args: '{ "a": 19, "b": 23 }',
      outcome: "42",
    });
    expect(summarize(run[3], undefined).outcome).toBeNull();
  });

  it("shows unparsable arguments verbatim instead of guessing", () => {
    expect(parseArguments('{"a": 1')).toEqual({
      parsed: false,
      text: '{"a": 1',
    });
    expect(parseArguments('{"a":1}')).toEqual({
      parsed: true,
      text: '{\n  "a": 1\n}',
    });
  });
});
