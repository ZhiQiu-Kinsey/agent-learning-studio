import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, RotateCcw, X } from "lucide-react";
import JellyRadio from "../../components/react-bits/JellyRadio";
import { Button } from "../../components/ui/button";
import type { MicroQuiz } from "../types.gen";

/** One question inside the reading flow; every option explains itself after answering. */
export function MicroQuizBlock({ block }: { block: MicroQuiz }) {
  const { t } = useTranslation("blocks", { keyPrefix: "microQuiz" });
  const { question } = block;
  const [answer, setAnswer] = useState("");
  const [checked, setChecked] = useState(false);
  const correct = answer === question.correct;
  const feedbackId = `${block.id}-feedback`;
  return (
    <section
      className="micro-quiz"
      aria-label={t("region")}
      data-testid="micro-quiz"
    >
      <span className="reading-eyebrow">{t("eyebrow")}</span>
      <fieldset disabled={checked}>
        <legend>{question.prompt}</legend>
        <JellyRadio
          className="quiz-jelly-options"
          ariaLabel={question.prompt}
          ariaDescribedBy={checked ? feedbackId : undefined}
          value={answer}
          disabled={checked}
          items={question.options.map((option) => ({
            value: option.id,
            label: option.text,
          }))}
          onChange={setAnswer}
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
      </fieldset>
      {checked ? (
        <div
          className="micro-quiz-feedback"
          id={feedbackId}
          data-correct={correct}
        >
          <strong>
            {correct ? <Check size={15} /> : <X size={15} />}
            {correct ? t("correct") : t("incorrect")}
          </strong>
          <ul>
            {question.options.map((option) => (
              <li
                key={option.id}
                data-correct={option.id === question.correct || undefined}
              >
                <span>{option.text}</span>
                {option.feedback && <small>{option.feedback}</small>}
              </li>
            ))}
          </ul>
          <p>{question.explanation}</p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setChecked(false);
              setAnswer("");
            }}
          >
            <RotateCcw size={14} />
            {t("retry")}
          </Button>
        </div>
      ) : (
        <Button size="sm" disabled={!answer} onClick={() => setChecked(true)}>
          {t("submit")}
        </Button>
      )}
    </section>
  );
}
