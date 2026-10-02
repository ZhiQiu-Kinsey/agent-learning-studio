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
    { action: "narrate", text: "先看模型" },
    { action: "spotlight", target: "model" },
    { action: "seek", observe: "call" },
    { action: "narrate", text: "再看 Python" },
    { action: "spotlight", target: "tool" },
    { action: "highlight", observe: "result" },
    { action: "seek", observe: "never" },
  ],
  conclusion: null,
};

describe("resolveGuide", () => {
  it("jumping to a step re-applies the latest narration, spotlight and evidence before it", () => {
    const frame = resolveGuide(experiment, run, 4);
    expect(frame).toMatchObject({
      step: 4,
      total: 7,
      narration: "再看 Python",
      spotlight: "tool",
      evidence: { observe: "call", found: true, index: 3, highlight: false },
    });
  });

  it("highlights the value at the selector path from the real run", () => {
    expect(resolveGuide(experiment, run, 5).evidence).toMatchObject({
      observe: "result",
      found: true,
      index: 4,
      value: 42,
      highlight: true,
      path: "data.result.result",
    });
  });

  it("reports missing evidence instead of pointing elsewhere", () => {
    expect(resolveGuide(experiment, run, 6).evidence).toEqual({
      observe: "never",
      text: "不会出现的证据",
      found: false,
    });
    expect(resolveGuide(experiment, [], 2).evidence).toMatchObject({
      found: false,
    });
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
