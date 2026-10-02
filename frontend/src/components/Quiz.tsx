import { useId, useState } from "react";
import { Check, Circle, RotateCcw, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  optionFeedback,
  readyToSubmit,
  scoreQuiz,
  type OptionVerdict,
  type QuizScore,
} from "../content/quiz";
import { confidenceLevels, type Confidence } from "../progress/model";
import type { QuizQuestion } from "../types";
import { Button } from "./ui/button";
import JellyRadio from "./react-bits/JellyRadio";

const verdictIcon: Record<OptionVerdict, typeof Check> = {
  "correct-chosen": Check,
  "correct-missed": Check,
  "wrong-chosen": X,
  "wrong-other": Circle,
};

const letter = (index: number) => String.fromCharCode(65 + index);

/**
 * 自测：可选先评信心（3 档）再作答；检查后逐个选项说明对错，再给整题解析。
 * 计分只在提交时回调一次，调用方决定是否写入本机进度。
 */
export function Quiz({
  questions,
  onScored,
  confidence = false,
  title,
}: {
  questions: QuizQuestion[];
  onScored?: (
    correct: number,
    total: number,
    answers: QuizScore["answers"],
  ) => void;
  /** 先让学习者评信心，再开放选项。 */
  confidence?: boolean;
  title?: string | null;
}) {
  const { t } = useTranslation("quiz");
  const quizId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [levels, setLevels] = useState<Record<string, Confidence>>({});
  const [checked, setChecked] = useState(false);
  if (!questions.length) return <div className="quiz-empty">{t("empty")}</div>;

  const answered = questions.filter((question) => answers[question.id]).length;
  const rated = questions.filter((question) => levels[question.id]).length;
  const ready = readyToSubmit(questions, answers, levels, confidence);
  const score = scoreQuiz(questions, answers, confidence ? levels : {});

  return (
    <form
      className="quiz-pane"
      data-testid="quiz-pane"
      onSubmit={(event) => {
        event.preventDefault();
        if (!ready || checked) return;
        setChecked(true);
        onScored?.(score.correct, score.total, score.answers);
      }}
    >
      <div className="quiz-intro">
        <div className="quiz-eyebrow">{t("eyebrow")}</div>
        <h2>{title || t("title")}</h2>
        <p>{confidence ? t("introConfidence") : t("intro")}</p>
      </div>
      {questions.map((question, index) => {
        const isCorrect = answers[question.id] === question.correct;
        const feedbackId = `${quizId}-${question.id}-feedback`;
        const lockId = `${quizId}-${question.id}-lock`;
        const level = levels[question.id];
        const locked = confidence && !level && !checked;
        return (
          <fieldset
            className="quiz-question"
            data-testid="quiz-question"
            key={question.id}
            disabled={checked}
          >
            <legend>
              <span aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              {question.prompt}
            </legend>
            {confidence && (
              <div className="quiz-confidence" data-testid="quiz-confidence">
                <span className="quiz-confidence-prompt">
                  {t("confidence.prompt")}
                </span>
                <JellyRadio
                  className="quiz-confidence-options"
                  ariaLabel={t("confidence.region")}
                  value={level ?? ""}
                  disabled={checked}
                  items={confidenceLevels.map((value) => ({
                    value,
                    label: t(`confidence.${value}`),
                  }))}
                  onChange={(value) =>
                    setLevels((previous) => ({
                      ...previous,
                      [question.id]: value as Confidence,
                    }))
                  }
                  size="sm"
                  chipColor="var(--surface)"
                  activeColor="var(--accent-soft)"
                  textColor="var(--text-muted)"
                  activeTextColor="var(--text-accent)"
                  radius={999}
                  swell={0.04}
                  barge={2}
                  shrink={0}
                  jelly={0.4}
                />
              </div>
            )}
            <div
              className="quiz-options"
              aria-describedby={checked ? feedbackId : undefined}
            >
              {locked && (
                <p className="quiz-locked" id={lockId}>
                  {t("confidence.locked")}
                </p>
              )}
              <JellyRadio
                className="quiz-jelly-options"
                ariaLabel={question.prompt}
                ariaDescribedBy={
                  checked ? feedbackId : locked ? lockId : undefined
                }
                value={answers[question.id] ?? ""}
                disabled={checked || locked}
                items={question.options.map((option, optionIndex) => ({
                  value: option.id,
                  label: (
                    <span className="quiz-option-label">
                      <span className="quiz-option-letter" aria-hidden="true">
                        {letter(optionIndex)}
                      </span>
                      <span>{option.text}</span>
                    </span>
                  ),
                }))}
                onChange={(value) =>
                  setAnswers((previous) => ({
                    ...previous,
                    [question.id]: value,
                  }))
                }
                chipColor="var(--surface)"
                activeColor="var(--surface-muted)"
                textColor="var(--text-muted)"
                activeTextColor="var(--text-accent)"
                radius={10}
                swell={0.015}
                barge={0}
                shrink={0}
                jelly={0.25}
              />
            </div>
            {checked && (
              <div
                className={`quiz-feedback ${isCorrect ? "is-correct" : "is-incorrect"}`}
                id={feedbackId}
                data-testid="quiz-feedback"
              >
                <strong>
                  {isCorrect ? <Check size={15} /> : <X size={15} />}
                  {isCorrect ? t("correct") : t("incorrect")}
                </strong>
                <ul
                  className="quiz-option-feedback"
                  aria-label={t("options.region")}
                >
                  {optionFeedback(question, answers[question.id]).map(
                    (option, optionIndex) => {
                      const Icon = verdictIcon[option.verdict];
                      return (
                        <li
                          key={option.id}
                          data-testid="quiz-option-feedback"
                          data-option={option.id}
                          data-verdict={option.verdict}
                        >
                          <span className="quiz-verdict">
                            <Icon size={13} aria-hidden="true" />
                            {t(`verdict.${option.verdict}`)}
                          </span>
                          <span className="quiz-verdict-option">
                            <span aria-hidden="true">
                              {letter(optionIndex)}
                            </span>
                            {option.text}
                          </span>
                          {option.feedback && <p>{option.feedback}</p>}
                        </li>
                      );
                    },
                  )}
                </ul>
                <p className="quiz-explanation" data-testid="quiz-explanation">
                  <b>{t("explanation")}</b>
                  {question.explanation}
                </p>
                {confidence && level && (
                  <p className="quiz-confidence-recorded">
                    {t("confidence.recorded", {
                      level: t(`confidence.${level}`),
                    })}
                  </p>
                )}
              </div>
            )}
          </fieldset>
        );
      })}
      <div className="quiz-actions">
        <span className="quiz-status" role="status" aria-live="polite">
          {checked
            ? t("scored", { correct: score.correct, total: questions.length })
            : confidence
              ? t("progressConfidence", {
                  rated,
                  answered,
                  total: questions.length,
                })
              : t("progress", { answered, total: questions.length })}
        </span>
        {checked ? (
          <Button
            type="button"
            className="quiz-reset"
            onClick={() => {
              setAnswers({});
              setLevels({});
              setChecked(false);
            }}
          >
            <RotateCcw size={15} />
            {t("reset")}
          </Button>
        ) : (
          <Button className="quiz-submit" type="submit" disabled={!ready}>
            <Check size={15} />
            {t("submit")}
          </Button>
        )}
      </div>
    </form>
  );
}
