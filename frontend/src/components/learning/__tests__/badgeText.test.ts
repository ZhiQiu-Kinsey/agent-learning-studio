import { describe, expect, it } from "vitest";
import { clampLines, fitText, tokenize, wrapText } from "../badgeText";

// Monospace stand-in for canvas measureText: every character is one unit
// wide, CJK characters two.
const width = (text: string) =>
  Array.from(text).reduce(
    (sum, char) => sum + (/[　-鿿＀-￯]/u.test(char) ? 2 : 1),
    0,
  );

describe("tokenize", () => {
  it("keeps Latin words whole and splits CJK per character", () => {
    expect(tokenize("One model request")).toEqual([
      "One",
      " ",
      "model",
      " ",
      "request",
    ]);
    expect(tokenize("一次模型请求")).toEqual(["一", "次", "模", "型", "请", "求"]);
  });

  it("keeps closing punctuation with the character before it", () => {
    expect(tokenize("程序，重发")).toEqual(["程", "序，", "重", "发"]);
    expect(tokenize("Agent：循环")).toEqual(["Agent：", "循", "环"]);
  });
});

describe("wrapText", () => {
  it("breaks English titles between words, never mid-word", () => {
    expect(wrapText("One model request", 12, width)).toEqual([
      "One model",
      "request",
    ]);
    expect(
      wrapText("Multi-turn conversation: the program resends history", 20, width),
    ).toEqual(["Multi-turn", "conversation: the", "program resends", "history"]);
  });

  it("breaks CJK text between characters", () => {
    expect(wrapText("多轮对话：程序重发历史", 10, width)).toEqual([
      "多轮对话：",
      "程序重发历",
      "史",
    ]);
  });

  it("wraps mixed text at spaces and CJK boundaries", () => {
    expect(wrapText("第一个 Agent 循环", 12, width)).toEqual([
      "第一个 Agent",
      "循环",
    ]);
  });

  it("breaks a single over-long word by character", () => {
    expect(wrapText("Supercalifragilistic", 8, width)).toEqual([
      "Supercal",
      "ifragili",
      "stic",
    ]);
  });

  it("never returns a line wider than the limit", () => {
    const text = "Executing tools and returning results 执行工具并把结果送回模型";
    for (const max of [6, 9, 14, 23]) {
      for (const line of wrapText(text, max, width))
        expect(width(line)).toBeLessThanOrEqual(max);
    }
  });

  it("keeps inner spaces and trims line ends", () => {
    expect(wrapText("  a   b  ", 10, width)).toEqual(["a   b"]);
    expect(wrapText("a   b", 3, width)).toEqual(["a", "b"]);
    expect(wrapText("", 10, width)).toEqual([]);
  });
});

describe("clampLines", () => {
  it("leaves text that fits untouched", () => {
    expect(clampLines(["a", "b"], 2, 5, width)).toEqual(["a", "b"]);
  });

  it("ends the last kept line with an ellipsis that still fits", () => {
    const lines = clampLines(["abcde", "fghij", "klm"], 2, 5, width);
    expect(lines).toEqual(["abcde", "fghi…"]);
    expect(width(lines[1])).toBeLessThanOrEqual(5);
  });
});

describe("fitText", () => {
  // At size s each unit is s/10 wide.
  const scaled = (text: string, size: number) => (width(text) * size) / 10;
  const steps = [
    { size: 20, maxLines: 1 },
    { size: 10, maxLines: 2 },
  ];

  it("keeps the largest size that fits", () => {
    expect(fitText("Runs", 10, steps, scaled)).toEqual({
      size: 20,
      lines: ["Runs"],
    });
  });

  it("shrinks and wraps before cutting", () => {
    expect(fitText("Scenes opened", 10, steps, scaled)).toEqual({
      size: 10,
      lines: ["Scenes", "opened"],
    });
  });

  it("clamps with an ellipsis at the last step", () => {
    const fitted = fitText("one two three four", 6, steps, scaled);
    expect(fitted.size).toBe(10);
    expect(fitted.lines).toEqual(["one", "two…"]);
  });
});
