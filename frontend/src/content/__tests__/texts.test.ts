import { describe, expect, it } from "vitest";
import { blockTexts, readingTexts } from "../glossary/texts";
import {
  assignFirstOccurrences,
  buildMatcher,
  type GlossaryEntry,
} from "../glossary/match";
import type { Block } from "../view";

const toolResult = {
  id: "tool-result",
  zh: "工具结果",
  en: "Tool Result",
  aliases: [],
  definition: "d",
} as GlossaryEntry;

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

describe("readingTexts", () => {
  const prose = (id: string, ...paragraphs: string[]) =>
    ({ id, type: "prose", title: id, paragraphs }) as Block;

  it("puts every deep-dive after the main text so the main text claims terms first", () => {
    const blocks = [
      deepDive("early summary"),
      prose("a", "main a"),
      { ...deepDive(null), id: "dive2", paragraphs: ["late dive"] } as Block,
      prose("b", "main b"),
    ];
    expect(readingTexts(blocks)).toEqual([
      "main a",
      "main b",
      "early summary",
      "first",
      "second",
      "late dive",
    ]);
  });

  it("lets a term used in both the main text and a deep-dive be owned by the main text", () => {
    const matcher = buildMatcher([toolResult])!;
    const blocks = [
      { ...deepDive(null), paragraphs: ["深入里讲工具结果"] } as Block,
      prose("a", "正文里讲工具结果"),
    ];
    const owners = assignFirstOccurrences(readingTexts(blocks), matcher);
    expect(owners.has("正文里讲工具结果")).toBe(true);
    expect(owners.has("深入里讲工具结果")).toBe(false);
  });

  it("still lets a deep-dive own a term that only it uses", () => {
    const matcher = buildMatcher([toolResult])!;
    const blocks = [
      { ...deepDive(null), paragraphs: ["深入里讲工具结果"] } as Block,
      prose("a", "正文没有这个词"),
    ];
    const owners = assignFirstOccurrences(readingTexts(blocks), matcher);
    expect(owners.has("深入里讲工具结果")).toBe(true);
  });
});
