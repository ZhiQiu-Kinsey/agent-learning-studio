import { describe, expect, it } from "vitest";
import type { Chapter } from "../../../content/types.gen";
import { chapterGlossaryTexts, readChapter } from "../chapters";

const chapter = {
  id: "demo",
  title: "Demo",
  eyebrow: "",
  summary: "",
  estimated_minutes: 1,
  next_label: null,
  illustrations: {},
  scenes: {
    understand: {
      blocks: [
        {
          id: "lead",
          type: "deep-dive",
          title: "t",
          summary: "lead summary",
          paragraphs: ["lead body"],
        },
        { id: "one", type: "prose", title: "one", paragraphs: ["p1"] },
        { id: "mis", type: "misconception", claim: "c1", correction: "c2" },
        {
          id: "quiz",
          type: "micro-quiz",
          question: {
            id: "q",
            prompt: "not marked",
            options: [],
            correct: "a",
            explanation: "",
          },
        },
        { id: "two", type: "prose", title: "two", paragraphs: ["p2"] },
        {
          id: "dive",
          type: "deep-dive",
          title: "t",
          summary: null,
          paragraphs: ["dive body"],
        },
      ],
    },
  },
} as unknown as Chapter;

describe("chapterGlossaryTexts", () => {
  it("follows the render order, but deep-dives come after all the main text", () => {
    expect(chapterGlossaryTexts(readChapter(chapter))).toEqual([
      "p1",
      "c1",
      "c2",
      "p2",
      "lead summary",
      "lead body",
      "dive body",
    ]);
  });
});
