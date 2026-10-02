import type { Confidence, QuizAnswer } from "../progress/model";
import type { QuizQuestion } from "./types.gen";

/**
 * 选项级反馈：作答后每个选项都要说明对或错的原因。
 * - correct-chosen：选中且正确；correct-missed：正确答案但没选；
 * - wrong-chosen：选中但错误；wrong-other：没选的错误选项。
 */
export type OptionVerdict =
  | "correct-chosen"
  | "correct-missed"
  | "wrong-chosen"
  | "wrong-other";

export interface OptionFeedback {
  id: string;
  text: string;
  verdict: OptionVerdict;
  /** 作者写的选项解释；内容缺失时为 null，界面只标对错，不编造理由。 */
  feedback: string | null;
}

export function optionFeedback(
  question: QuizQuestion,
  chosen: string | undefined,
): OptionFeedback[] {
  return question.options.map((option) => {
    const isCorrect = option.id === question.correct;
    const isChosen = option.id === chosen;
    return {
      id: option.id,
      text: option.text,
      verdict: isCorrect
        ? isChosen
          ? "correct-chosen"
          : "correct-missed"
        : isChosen
          ? "wrong-chosen"
          : "wrong-other",
      feedback: option.feedback ?? null,
    };
  });
}

export interface QuizScore {
  correct: number;
  total: number;
  answers: Record<string, QuizAnswer>;
}

/** 只计已作答的题；未作答的题不会被当作答对或答错。 */
export function scoreQuiz(
  questions: readonly QuizQuestion[],
  chosen: Record<string, string | undefined>,
  confidence: Record<string, Confidence | undefined> = {},
): QuizScore {
  const answers: Record<string, QuizAnswer> = {};
  for (const question of questions) {
    const answer = chosen[question.id];
    if (!answer) continue;
    const level = confidence[question.id];
    answers[question.id] = {
      correct: answer === question.correct,
      ...(level ? { confidence: level } : {}),
    };
  }
  const values = Object.values(answers);
  return {
    correct: values.filter((answer) => answer.correct).length,
    total: values.length,
    answers,
  };
}

/** 题目都作答（需要信心时也都评过信心）才能提交。 */
export function readyToSubmit(
  questions: readonly QuizQuestion[],
  chosen: Record<string, string | undefined>,
  confidence: Record<string, Confidence | undefined>,
  needsConfidence: boolean,
): boolean {
  return questions.every(
    (question) =>
      !!chosen[question.id] && (!needsConfidence || !!confidence[question.id]),
  );
}

export type ConfidenceSummary = Record<
  Confidence,
  { answered: number; correct: number }
>;

/** 按信心档位汇总已记录的作答：每档答了几题、答对几题。 */
export function summarizeConfidence(
  answers: Iterable<QuizAnswer>,
): ConfidenceSummary {
  const summary: ConfidenceSummary = {
    low: { answered: 0, correct: 0 },
    medium: { answered: 0, correct: 0 },
    high: { answered: 0, correct: 0 },
  };
  for (const answer of answers) {
    if (!answer.confidence) continue;
    summary[answer.confidence].answered++;
    if (answer.correct) summary[answer.confidence].correct++;
  }
  return summary;
}
