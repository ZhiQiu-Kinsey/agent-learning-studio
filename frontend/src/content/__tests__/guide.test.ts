import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { observeStatus, resolveGuide } from "../guide";
import type { Experiment } from "../types.gen";
import both from "../../stage/__fixtures__/lesson-1-both.json";

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
  guide: [
    { text: "先看模型", observe: null, stage: null },
    { text: "这是模型提出的调用", observe: "call", stage: "model" },
    { text: "这是 Python 的结果", observe: "result", stage: "tool" },
    { text: "这一条这次没出现", observe: "never", stage: null },
  ],
  conclusion: null,
};

describe("resolveGuide", () => {
  it("gives each step its own sentence, stage role and evidence", () => {
    expect(resolveGuide(experiment, run, 0)).toMatchObject({
      step: 0,
      total: 4,
      text: "先看模型",
      stage: null,
      evidence: null,
    });
    expect(resolveGuide(experiment, run, 1)).toMatchObject({
      step: 1,
      text: "这是模型提出的调用",
      stage: "model",
      evidence: { observe: "call", found: true, index: 3 },
    });
  });

  it("points at the value at the selector path from the real run", () => {
    expect(resolveGuide(experiment, run, 2)).toMatchObject({
      text: "这是 Python 的结果",
      stage: "tool",
      evidence: {
        observe: "result",
        found: true,
        index: 4,
        value: 42,
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

  it("keeps unmatched evidence pending while the run is still going", () => {
    expect(
      observeStatus(experiment, run, true).map((item) => item.status),
    ).toEqual(["found", "found", "pending", "manual"]);
    expect(
      observeStatus(experiment, [], true).map((item) => item.status),
    ).toEqual(["no-run", "no-run", "no-run", "manual"]);
  });
});
