import { describe, expect, it } from "vitest";
import {
  optionFeedback,
  readyToSubmit,
  scoreQuiz,
  summarizeConfidence,
} from "../quiz";
import type { QuizQuestion } from "../types.gen";

const question = (id: string, feedback = true): QuizQuestion => ({
  id,
  prompt: `prompt ${id}`,
  correct: "b",
  explanation: `why ${id}`,
  options: [
    { id: "a", text: "A", feedback: feedback ? "a is wrong because" : null },
    { id: "b", text: "B", feedback: feedback ? "b is right because" : null },
    { id: "c", text: "C", feedback: feedback ? "c is wrong because" : null },
  ],
});

describe("option-level feedback", () => {
  it("explains every option, right and wrong, relative to the learner's choice", () => {
    expect(
      optionFeedback(question("q"), "a").map(({ id, verdict, feedback }) => [
        id,
        verdict,
        feedback,
      ]),
    ).toEqual([
      ["a", "wrong-chosen", "a is wrong because"],
      ["b", "correct-missed", "b is right because"],
      ["c", "wrong-other", "c is wrong because"],
    ]);
    expect(optionFeedback(question("q"), "b").map((item) => item.verdict)).toEqual([
      "wrong-other",
      "correct-chosen",
      "wrong-other",
    ]);
  });

  it("never invents an explanation the content does not have", () => {
    expect(
      optionFeedback(question("q", false), "b").every(
        (item) => item.feedback === null,
      ),
    ).toBe(true);
  });
});

describe("quiz scoring", () => {
  const questions = [question("q1"), question("q2"), question("q3")];

  it("needs every answer, and every confidence when the quiz asks for it", () => {
    const chosen = { q1: "b", q2: "a", q3: "b" };
    expect(readyToSubmit(questions, { q1: "b" }, {}, false)).toBe(false);
    expect(readyToSubmit(questions, chosen, {}, false)).toBe(true);
    expect(readyToSubmit(questions, chosen, { q1: "low" }, true)).toBe(false);
    expect(
      readyToSubmit(
        questions,
        chosen,
        { q1: "low", q2: "high", q3: "medium" },
        true,
      ),
    ).toBe(true);
  });

  it("scores answered questions and keeps each confidence with its result", () => {
    expect(
      scoreQuiz(
        questions,
        { q1: "b", q2: "a", q3: "b" },
        { q1: "low", q2: "high", q3: "high" },
      ),
    ).toEqual({
      correct: 2,
      total: 3,
      answers: {
        q1: { correct: true, confidence: "low" },
        q2: { correct: false, confidence: "high" },
        q3: { correct: true, confidence: "high" },
      },
    });
    // 没评信心的题不写信心；没作答的题不计入。
    expect(scoreQuiz(questions, { q1: "b" })).toEqual({
      correct: 1,
      total: 1,
      answers: { q1: { correct: true } },
    });
  });

  it("summarizes answers by confidence level", () => {
    expect(
      summarizeConfidence([
        { correct: true, confidence: "high" },
        { correct: false, confidence: "high" },
        { correct: true, confidence: "low" },
        { correct: true },
      ]),
    ).toEqual({
      low: { answered: 1, correct: 1 },
      medium: { answered: 0, correct: 0 },
      high: { answered: 2, correct: 1 },
    });
  });
});
