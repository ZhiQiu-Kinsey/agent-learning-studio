import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { guideStops, observeStatus, resolveGuide } from "../guide";
import type { Experiment } from "../types.gen";
import both from "../../stage/__fixtures__/lesson-1-both.json";

const run = both as Trace[];
const selector = (patch: Record<string, unknown>) => ({
  event: null,
  round: null,
  path: null,
  span_kind: null,
  name: null,
  ...patch,
});

const experiment: Experiment = {
  id: "explore",
  title: "工具选择",
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
    { id: "legacy", text: "旧的文字观察点", selector: null },
  ],
  // Authored like the lessons: the actions before a narration locate the
  // evidence that sentence talks about.
  guide: [
    { action: "narrate", text: "先看模型" },
    { action: "spotlight", target: "model" },
    { action: "seek", observe: "call" },
    { action: "narrate", text: "这是模型提出的调用" },
    { action: "spotlight", target: "tool" },
    { action: "highlight", observe: "result" },
    { action: "narrate", text: "这是 Python 的结果" },
    { action: "seek", observe: "never" },
  ],
  conclusion: null,
};

describe("guideStops", () => {
  it("makes one step per sentence, plus one for trailing actions", () => {
    expect(guideStops(experiment)).toEqual([0, 3, 6, 7]);
    expect(guideStops({ ...experiment, guide: [] })).toEqual([]);
  });
});

describe("resolveGuide", () => {
  it("pairs each sentence with the evidence located just before it", () => {
    expect(resolveGuide(experiment, run, 0)).toMatchObject({
      step: 0,
      total: 4,
      narration: "先看模型",
      spotlight: null,
      evidence: null,
    });
    expect(resolveGuide(experiment, run, 1)).toMatchObject({
      step: 1,
      narration: "这是模型提出的调用",
      spotlight: "model",
      evidence: { observe: "call", found: true, index: 3, highlight: false },
    });
  });

  it("never shows the same sentence on two consecutive steps", () => {
    const sentences = [0, 1, 2].map(
      (step) => resolveGuide(experiment, run, step).narration,
    );
    expect(new Set(sentences).size).toBe(sentences.length);
  });

  it("highlights the value at the selector path from the real run", () => {
    expect(resolveGuide(experiment, run, 2)).toMatchObject({
      narration: "这是 Python 的结果",
      spotlight: "tool",
      evidence: {
        observe: "result",
        found: true,
        index: 4,
        value: 42,
        highlight: true,
        path: "data.result.result",
      },
    });
  });

  it("reports missing evidence instead of pointing elsewhere", () => {
    expect(resolveGuide(experiment, run, 3).evidence).toEqual({
      observe: "never",
      text: "不会出现的证据",
      found: false,
    });
    expect(resolveGuide(experiment, [], 1).evidence).toMatchObject({
      found: false,
    });
  });

  it("clamps out-of-range steps to the last one", () => {
    expect(resolveGuide(experiment, run, 99).step).toBe(3);
  });
});

describe("observeStatus", () => {
  it("distinguishes no run, found and missing evidence", () => {
    expect(
      observeStatus(experiment, []).map((item) => item.status),
    ).toEqual(["no-run", "no-run", "no-run", "manual"]);
    expect(observeStatus(experiment, run).map((item) => item.status)).toEqual([
      "found",
      "found",
      "missing",
      "manual",
    ]);
  });
});
