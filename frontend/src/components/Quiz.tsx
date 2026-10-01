import { useId, useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { QuizQuestion } from "../types";
import { Button } from "./ui/button";
import JellyRadio from "./react-bits/JellyRadio";

export function Quiz({
  questions,
  onScored,
}: {
  questions: QuizQuestion[];
  onScored?: (correct: number, total: number) => void;
}) {
  const { t } = useTranslation("quiz");
  const quizId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);
  if (!questions.length) return <div className="quiz-empty">{t("empty")}</div>;

  const answered = questions.filter((question) => answers[question.id]).length;
  const correct = questions.filter(
    (question) => answers[question.id] === question.correct,
  ).length;

  return (
    <form
      className="quiz-pane"
      data-testid="quiz-pane"
      onSubmit={(event) => {
        event.preventDefault();
        if (answered !== questions.length) return;
        setChecked(true);
        onScored?.(correct, questions.length);
      }}
    >
      <div className="quiz-intro">
        <div className="quiz-eyebrow">{t("eyebrow")}</div>
        <h2>{t("title")}</h2>
        <p>{t("intro")}</p>
      </div>
      {questions.map((question, index) => {
        const isCorrect = answers[question.id] === question.correct;
        const feedbackId = `${quizId}-${question.id}-feedback`;
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
            <div
              className="quiz-options"
              aria-describedby={checked ? feedbackId : undefined}
            >
              <JellyRadio
                className="quiz-jelly-options"
                ariaLabel={question.prompt}
                ariaDescribedBy={checked ? feedbackId : undefined}
                value={answers[question.id] ?? ""}
                disabled={checked}
                items={question.options.map((option, optionIndex) => ({
                  value: option.id,
                  label: (
                    <span className="quiz-option-label">
                      <span className="quiz-option-letter" aria-hidden="true">
                        {String.fromCharCode(65 + optionIndex)}
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
                {!isCorrect && (
                  <p className="quiz-correct-answer">
                    {t("reference")}
                    {
                      question.options.find(
                        (option) => option.id === question.correct,
                      )?.text
                    }
                  </p>
                )}
                <p>{question.explanation}</p>
              </div>
            )}
          </fieldset>
        );
      })}
      <div className="quiz-actions">
        <span className="quiz-status" role="status" aria-live="polite">
          {checked
            ? t("scored", { correct, total: questions.length })
            : t("progress", { answered, total: questions.length })}
        </span>
        {checked ? (
          <Button
            type="button"
            className="quiz-reset"
            onClick={() => {
              setAnswers({});
              setChecked(false);
            }}
          >
            <RotateCcw size={15} />
            {t("reset")}
          </Button>
        ) : (
          <Button
            className="quiz-submit"
            type="submit"
            disabled={answered !== questions.length}
          >
            <Check size={15} />
            {t("submit")}
          </Button>
        )}
      </div>
    </form>
  );
}
