import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import both from "../../stage/__fixtures__/lesson-1-both.json";
import { huntState, judgeHunt, ownRunEvents, unmetConditions } from "../traceHunt";
import type { Selector } from "../types.gen";

const run = both as Trace[];
const target = (selector: Partial<Selector>): Selector => ({
  event: null,
  round: null,
  path: null,
  span_kind: null,
  name: null,
  nth: null,
  ...selector,
});
// 第 1 课：模型第一次在请求里看到工具结果。
const sawResult = target({
  event: "request",
  path: "data.body.messages[3].tool_call_id",
});

describe("trace hunt state", () => {
  it("asks for a run first and waits for it to finish", () => {
    expect(huntState(sawResult, [], false)).toEqual({ status: "no-run" });
    expect(huntState(sawResult, run.slice(0, 3), true).status).toBe("running");
  });

  it("lists the learner's own events and the indices that satisfy the target", () => {
    const state = huntState(sawResult, run, false);
    expect(state.status).toBe("ready");
    if (state.status !== "ready") return;
    expect(state.events).toHaveLength(run.length);
    expect(state.targets).toEqual([7]);
  });

  it("says the run lacks the evidence instead of pointing elsewhere", () => {
    const state = huntState(
      target({ event: "tool_result", path: "data.result.error_type" }),
      run,
      false,
    );
    expect(state.status).toBe("no-evidence");
  });

  it("never treats recordings or illustrations as the learner's evidence", () => {
    const recorded = run.map((event) => ({
      ...event,
      provenance: "recorded_run" as const,
    }));
    const illustration = run.map((event) => ({
      ...event,
      provenance: "illustration" as const,
    }));
    expect(huntState(sawResult, recorded, false)).toEqual({ status: "no-run" });
    expect(huntState(sawResult, illustration, false)).toEqual({ status: "no-run" });
    // 旧版事件没有 provenance，视为本机真实运行。
    const legacy = run.map(({ provenance: _, ...event }) => event as Trace);
    expect(ownRunEvents(legacy)).toHaveLength(run.length);
  });
});

describe("trace hunt verdict", () => {
  it("accepts any event the selector engine matches", () => {
    expect(judgeHunt(sawResult, run, 7)).toEqual({ correct: true });
    const anyToolCall = target({ event: "tool_call" });
    expect(judgeHunt(anyToolCall, run, 3)).toEqual({ correct: true });
    expect(judgeHunt(anyToolCall, run, 5)).toEqual({ correct: true });
  });

  it("names the conditions a wrong pick does not meet", () => {
    // 第 1 轮请求：类型对了，但还没有工具回执。
    expect(judgeHunt(sawResult, run, 1)).toEqual({
      correct: false,
      unmet: ["path"],
    });
    // tool_result 是 Python 的执行结果，模型此时还没看到它。
    expect(judgeHunt(sawResult, run, 4)).toEqual({
      correct: false,
      unmet: ["event", "path"],
    });
    const second = target({ event: "tool_call", round: 2, name: "add_numbers" });
    expect(unmetConditions(second, run[3])).toEqual(["round"]);
    expect(unmetConditions(second, run[5])).toEqual(["round", "name"]);
  });

  it("with nth, accepts only that hit and says when the order is wrong", () => {
    const secondCall = target({ event: "tool_call", nth: 2 });
    expect(huntState(secondCall, run, false)).toMatchObject({ targets: [5] });
    expect(judgeHunt(secondCall, run, 5)).toEqual({ correct: true });
    // 第一个 tool_call 满足全部条件，只是顺序不对。
    expect(judgeHunt(secondCall, run, 3)).toEqual({
      correct: false,
      unmet: ["nth"],
    });
    // 条件本身不满足时只列条件，不再提顺序。
    expect(judgeHunt(secondCall, run, 4)).toEqual({
      correct: false,
      unmet: ["event"],
    });
    expect(
      huntState(target({ event: "tool_call", nth: 3 }), run, false).status,
    ).toBe("no-evidence");
  });
});
