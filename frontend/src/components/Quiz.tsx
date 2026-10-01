import { useId, useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";
import type { QuizQuestion } from "../types";
import { Button } from "./ui/button";
import JellyRadio from "./react-bits/JellyRadio";

export function Quiz({ questions }: { questions: QuizQuestion[] }) {
  const quizId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);
  if (!questions.length)
    return <div className="quiz-empty">这节课暂未提供自测题。</div>;

  const answered = questions.filter((question) => answers[question.id]).length;
  const correct = questions.filter(
    (question) => answers[question.id] === question.correct_option,
  ).length;

  return (
    <form
      className="quiz-pane"
      onSubmit={(event) => {
        event.preventDefault();
        if (answered === questions.length) setChecked(true);
      }}
    >
      <div className="quiz-intro">
        <div className="quiz-eyebrow">CHECK YOUR UNDERSTANDING</div>
        <h2>检验你的理解</h2>
        <p>
          每题选择一个答案，检查后查看解析。你可以回到导读或源码，再重新作答。
        </p>
      </div>
      {questions.map((question, index) => {
        const isCorrect = answers[question.id] === question.correct_option;
        const feedbackId = `${quizId}-${question.id}-feedback`;
        return (
          <fieldset
            className="quiz-question"
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
              >
                <strong>
                  {isCorrect ? <Check size={15} /> : <X size={15} />}
                  {isCorrect ? "回答正确" : "这题还需要再想一想"}
                </strong>
                {!isCorrect && (
                  <p className="quiz-correct-answer">
                    参考答案：
                    {
                      question.options.find(
                        (option) => option.id === question.correct_option,
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
            ? `答对 ${correct} / ${questions.length} 题 · 阅读解析，再巩固一次`
            : `已作答 ${answered} / ${questions.length} 题`}
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
            重新作答
          </Button>
        ) : (
          <Button
            className="quiz-submit"
            type="submit"
            disabled={answered !== questions.length}
          >
            <Check size={15} />
            检查答案
          </Button>
        )}
      </div>
    </form>
  );
}
