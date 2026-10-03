import { describe, expect, it } from "vitest";
import type { Chapter } from "../types.gen";
import { chapterView } from "../view";

const prose = (id: string) => ({
  id,
  type: "prose",
  title: id,
  paragraphs: [`${id} text`],
  reveal: "none",
});
const flow = (id: string) => ({
  id,
  type: "flow",
  title: null,
  illustration: "demo",
  caption: null,
});
const quiz = (id: string) => ({
  id,
  type: "micro-quiz",
  question: {
    id: `${id}-q`,
    prompt: "pick one",
    options: [
      { id: "a", text: "A", feedback: null },
      { id: "b", text: "B", feedback: null },
    ],
    correct: "a",
    explanation: "because",
  },
});
const misconception = (id: string) => ({
  id,
  type: "misconception",
  claim: "claim",
  correction: "correction",
});
const deepDive = (id: string) => ({
  id,
  type: "deep-dive",
  title: id,
  summary: null,
  paragraphs: ["detail"],
});

function chapterOf(blocks: unknown[]): Chapter {
  return {
    id: "demo",
    title: "Demo",
    eyebrow: "",
    summary: "",
    estimated_minutes: 1,
    next_label: null,
    scenes: { understand: { blocks } },
    illustrations: {},
  } as unknown as Chapter;
}

describe("chapterView attachments", () => {
  it("keeps every attachment kind in its authored place, after the section before it", () => {
    const view = chapterView(
      chapterOf([
        prose("one"),
        flow("flow-1"),
        quiz("quiz-1"),
        prose("two"),
        misconception("mis-1"),
        deepDive("dive-1"),
        flow("flow-2"),
      ]),
    );
    expect(
      view.attachments.map(({ block, after }) => [block.id, block.type, after]),
    ).toEqual([
      ["flow-1", "flow", "one"],
      ["quiz-1", "micro-quiz", "one"],
      ["mis-1", "misconception", "two"],
      ["dive-1", "deep-dive", "two"],
      ["flow-2", "flow", "two"],
    ]);
  });

  it("counts only sections, never attachments", () => {
    const view = chapterView(
      chapterOf([
        quiz("quiz-1"),
        prose("one"),
        deepDive("dive-1"),
        prose("two"),
        misconception("mis-1"),
      ]),
    );
    expect(view.sections.map((section) => section.id)).toEqual(["one", "two"]);
    expect(view.attachments).toHaveLength(3);
  });

  it("leaves attachments before the first section with no anchor", () => {
    const view = chapterView(chapterOf([deepDive("dive-1"), prose("one")]));
    expect(view.attachments).toEqual([
      { block: expect.objectContaining({ id: "dive-1" }), after: null },
    ]);
  });

  it("ignores blocks that are neither sections nor attachments", () => {
    const view = chapterView(
      chapterOf([
        prose("one"),
        { id: "refs", type: "references", items: [] },
        { id: "objectives", type: "objectives", items: [] },
      ]),
    );
    expect(view.attachments).toEqual([]);
    expect(view.sections).toHaveLength(1);
  });
});
