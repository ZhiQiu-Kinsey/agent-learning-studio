import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import type { Trace } from "../../types";
import { evaluatePredict } from "../predict";
import type { Predict } from "../types.gen";

const storageKey = (lessonId: string, blockId: string) =>
  `agent-lab-predict:${lessonId}:${blockId}`;

function readPrediction(key: string): number | undefined {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? undefined : Number(raw);
  } catch {
    return undefined;
  }
}

/**
 * Write a prediction first, verify it in the lab. The comparison is computed
 * only from the learner's own real events of this lesson.
 */
export function PredictBlock({
  block,
  lessonId,
  events,
  onRun,
}: {
  block: Predict;
  lessonId: string;
  /** The current run's events; empty when this lesson has not been run. */
  events: readonly Trace[];
  onRun: () => void;
}) {
  const { t } = useTranslation("blocks", { keyPrefix: "predict" });
  const key = storageKey(lessonId, block.id);
  const [saved, setSaved] = useState(() => readPrediction(key));
  const [draft, setDraft] = useState(saved === undefined ? "" : String(saved));
  const outcome = evaluatePredict(block.rule, events, saved);
  const save = () => {
    const value = Number(draft);
    if (!Number.isInteger(value) || value < 0) return;
    setSaved(value);
    try {
      localStorage.setItem(key, String(value));
    } catch {
      /* Keep the prediction for this session. */
    }
  };
  return (
    <section
      className="predict-block"
      aria-label={t("region")}
      data-testid="predict-block"
    >
      <span className="reading-eyebrow">{t("eyebrow")}</span>
      <h3>{block.prompt}</h3>
      <p className="predict-help">{t("help")}</p>
      <div className="predict-row">
        <label htmlFor={`${block.id}-input`}>{t("input")}</label>
        <Input
          id={`${block.id}-input`}
          type="number"
          min={0}
          step={1}
          inputMode="numeric"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button
          size="sm"
          variant="outline"
          onClick={save}
          disabled={draft === ""}
        >
          {t("save")}
        </Button>
      </div>
      {saved !== undefined && (
        <p className="predict-saved">{t("saved", { prediction: saved })}</p>
      )}
      {outcome.status === "no-run" ? (
        <p className="predict-result" data-testid="predict-result">
          {t("noRun")}
        </p>
      ) : (
        <p
          className="predict-result"
          data-testid="predict-result"
          data-match={outcome.matches ?? undefined}
        >
          {t("actual", { actual: outcome.actual })}
          {outcome.matches !== null &&
            ` · ${outcome.matches ? t("match") : t("mismatch", { prediction: saved })}`}
        </p>
      )}
      <Button size="sm" onClick={onRun}>
        {t("go")}
        <ArrowRight size={14} />
      </Button>
    </section>
  );
}
