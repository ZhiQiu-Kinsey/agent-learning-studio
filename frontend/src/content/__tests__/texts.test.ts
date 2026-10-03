import { describe, expect, it } from "vitest";
import { blockTexts } from "../glossary/texts";
import type { Block } from "../view";

const deepDive = (summary: string | null) =>
  ({
    id: "dive",
    type: "deep-dive",
    title: "Title is not marked",
    summary,
    paragraphs: ["first", "second"],
  }) as Block;

describe("blockTexts for deep-dive", () => {
  it("lists the summary before the paragraphs, as the renderer shows them", () => {
    expect(blockTexts(deepDive("one line"))).toEqual([
      "one line",
      "first",
      "second",
    ]);
  });

  it("skips a missing summary and never includes the title", () => {
    expect(blockTexts(deepDive(null))).toEqual(["first", "second"]);
  });
});
