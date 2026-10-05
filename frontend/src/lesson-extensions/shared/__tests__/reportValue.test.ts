import { describe, expect, it } from "vitest";
import { LONG_CELL, reportValue, splitMetrics } from "../reportValue";

// Shapes taken from the context-compaction report (lesson.report).
const usage = {
  prompt_tokens: 462,
  total_tokens: 940,
  completion_tokens: 478,
  prompt_tokens_details: { cached_tokens: 0, text_tokens: 462 },
};
const summary = "目标：先查".repeat(30);

describe("reportValue", () => {
  it("keeps numbers as numbers and short words as body text", () => {
    expect(reportValue(5)).toEqual({ kind: "number", text: "5" });
    expect(reportValue(true)).toEqual({ kind: "number", text: "true" });
    expect(reportValue("80%")).toEqual({ kind: "number", text: "80%" });
    expect(reportValue("3/5")).toEqual({ kind: "number", text: "3/5" });
    expect(reportValue("keep_sources")).toEqual({
      kind: "text",
      text: "keep_sources",
    });
    expect(reportValue("未报告")).toEqual({ kind: "text", text: "未报告" });
  });

  it("shows usage as flattened key-value rows, from an object or a JSON string", () => {
    const pairs = [
      { key: "prompt_tokens", value: "462" },
      { key: "total_tokens", value: "940" },
      { key: "completion_tokens", value: "478" },
      { key: "prompt_tokens_details.cached_tokens", value: "0" },
      { key: "prompt_tokens_details.text_tokens", value: "462" },
    ];
    expect(reportValue(usage)).toEqual({ kind: "pairs", pairs });
    // Recorded runs carry usage as JSON text; the rows are the same.
    expect(reportValue(JSON.stringify(usage))).toEqual({
      kind: "pairs",
      pairs,
    });
  });

  it("folds long text and leaves non-object JSON-ish text alone", () => {
    expect(reportValue(summary)).toEqual({ kind: "long", text: summary });
    expect(reportValue("第一行\n第二行")).toMatchObject({ kind: "long" });
    expect(reportValue("{不是 JSON}")).toEqual({
      kind: "text",
      text: "{不是 JSON}",
    });
    expect(reportValue("{}")).toEqual({ kind: "text", text: "{}" });
  });

  it("lets table cells hold more text before folding", () => {
    const answer = "答".repeat(100);
    expect(reportValue(answer).kind).toBe("long");
    expect(reportValue(answer, LONG_CELL)).toEqual({
      kind: "text",
      text: answer,
    });
    expect(reportValue("答".repeat(LONG_CELL + 1), LONG_CELL).kind).toBe(
      "long",
    );
  });

  it("reports missing values as empty instead of inventing one", () => {
    expect(reportValue(null)).toEqual({ kind: "empty" });
    expect(reportValue(undefined)).toEqual({ kind: "empty" });
    expect(reportValue({})).toEqual({ kind: "empty" });
  });
});

describe("splitMetrics", () => {
  it("puts tiles first and long or object values on their own rows, in report order", () => {
    const metrics = [
      { label: "模型调用数", value: 5 },
      { label: "摘要请求的用量", value: JSON.stringify(usage) },
      { label: "摘要指令", value: "keep_sources" },
      { label: "摘要原文", value: summary },
      { label: "探针问题", value: "最早读取的那份资料来自哪一项？" },
    ];
    const { tiles, wide } = splitMetrics(metrics);
    expect(tiles.map((item) => item.metric.label)).toEqual([
      "模型调用数",
      "摘要指令",
      "探针问题",
    ]);
    expect(tiles.map((item) => item.shown.kind)).toEqual([
      "number",
      "text",
      "text",
    ]);
    expect(wide.map((item) => [item.metric.label, item.shown.kind])).toEqual([
      ["摘要请求的用量", "pairs"],
      ["摘要原文", "long"],
    ]);
    // Original positions survive for fallback labels ("指标 N").
    expect(wide.map((item) => item.index)).toEqual([1, 3]);
  });
});
