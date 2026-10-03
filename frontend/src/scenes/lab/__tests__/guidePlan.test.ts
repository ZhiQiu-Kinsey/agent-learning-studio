import { describe, expect, it } from "vitest";
import type { Trace } from "../../../types";
import type { Experiment } from "../../../content/types.gen";
import both from "../../../stage/__fixtures__/lesson-1-both.json";
import { guidePlan } from "../guidePlan";

const run = both as Trace[];
const selector = (patch: Record<string, unknown>) => ({
  event: null,
  round: null,
  path: null,
  span_kind: null,
  name: null,
  nth: null,
  ...patch,
});

const experiment: Experiment = {
  id: "loop",
  title: "一轮工具调用",
  hypothesis: null,
  predict: null,
  arms: [{ id: "sum", exercise: "sum", label: null, inputs: null }],
  observe: [
    {
      id: "call",
      text: "模型提出加法调用",
      selector: selector({ event: "tool_call", name: "add_numbers" }),
    },
    {
      id: "result",
      text: "Python 返回结果",
      selector: selector({ event: "tool_result", path: "data.result.result" }),
    },
    {
      id: "never",
      text: "不会出现的证据",
      selector: selector({ event: "tool_call", name: "delete_files" }),
    },
  ],
  guide: [
    { text: "先看这次运行", observe: null, stage: null },
    { text: "模型提出调用", observe: "call", stage: "model" },
    { text: "Python 的结果", observe: "result", stage: "tool" },
    { text: "运行层在中间转交", observe: null, stage: "runtime" },
    { text: "这一条没出现", observe: "never", stage: null },
  ],
  conclusion: null,
};

describe("guidePlan", () => {
  const plan = guidePlan(experiment, run);

  it("opens in the middle when a step has nothing to point at", () => {
    expect(plan[0].aim).toEqual({ kind: "center" });
  });

  it("aims at the real event, and at its field when the selector has a path", () => {
    expect(plan[1].aim).toEqual({
      kind: "evidence",
      index: 3,
      path: null,
      report: false,
    });
    expect(plan[2].aim).toEqual({
      kind: "evidence",
      index: 4,
      path: "data.result.result",
      report: false,
    });
  });

  it("frames a stage node when the step names a role but no evidence", () => {
    expect(plan[3].aim).toEqual({ kind: "stage", role: "runtime" });
  });

  it("never points elsewhere for evidence this run did not produce", () => {
    expect(plan[4].aim).toEqual({ kind: "center" });
    expect(plan[4].frame.evidence).toMatchObject({ found: false });
  });

  it("gives every step a stable id", () => {
    expect(plan.map((step) => step.id)).toEqual([
      "loop-0",
      "loop-1",
      "loop-2",
      "loop-3",
      "loop-4",
    ]);
  });
});
