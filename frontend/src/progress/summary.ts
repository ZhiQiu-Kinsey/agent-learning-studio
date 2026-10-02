import { summarizeConfidence } from "../content/quiz";
import { LEGACY_QUIZ_ID, type LessonProgress } from "./model";

/** 回顾页的全部数字都从本机进度推出；没有动作就是 0，不推断“已掌握”。 */
export function reviewNumbers(record: LessonProgress | undefined) {
  const quizzes = Object.values(record?.quizzes ?? {});
  const numbers = {
    runs: record?.runs.count ?? 0,
    quizCorrect: quizzes.reduce((sum, quiz) => sum + quiz.correct, 0),
    quizTotal: quizzes.reduce((sum, quiz) => sum + quiz.total, 0),
    quizAttempts: quizzes.reduce((sum, quiz) => sum + quiz.attempts, 0),
    hasLegacyQuiz: !!record?.quizzes[LEGACY_QUIZ_ID],
    checkpoints: Object.keys(record?.checkpoints ?? {}).length,
    evidence: Object.keys(record?.evidence ?? {}).length,
    confidence: summarizeConfidence(
      quizzes.flatMap((quiz) => Object.values(quiz.answers)),
    ),
  };
  return {
    ...numbers,
    hasActivity:
      numbers.runs > 0 ||
      numbers.quizAttempts > 0 ||
      numbers.checkpoints > 0 ||
      numbers.evidence > 0,
  };
}
