import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import type { StudioState } from "../../hooks/useStudio";
import { resolveGuide } from "../../content/guide";
import type { Experiment } from "../../content/types.gen";
import { Button } from "../../components/ui/button";

const preview = (value: unknown) => {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 80 ? `${text.slice(0, 79)}…` : text;
};

/**
 * Guided replay over the learner's own run: narration bubble, stage spotlight,
 * and seeking to the evidence. Keys: ← / → step through the guide, Esc exits;
 * typing in a field never triggers them.
 */
export function GuideBar({
  experiment,
  studio,
  step,
  onStep,
  onExit,
  onSpotlight,
}: {
  experiment: Experiment;
  studio: StudioState;
  step: number;
  onStep: (step: number) => void;
  onExit: () => void;
  onSpotlight: (role: string | null) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab.guide" });
  const frame = useMemo(
    () => resolveGuide(experiment, studio.events, step),
    [experiment, studio.events, step],
  );
  const evidence = frame.evidence;

  useEffect(() => {
    onSpotlight(frame.spotlight);
    if (evidence?.found && !studio.running) {
      studio.seek(evidence.index + 1);
      studio.selectEvent(evidence.index);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frame.step, frame.spotlight, evidence?.found ? evidence.index : -1]);

  useEffect(() => () => onSpotlight(null), [onSpotlight]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (
        target?.closest(
          "input, textarea, select, [contenteditable='true'], [role='slider']",
        )
      )
        return;
      if (event.key === "ArrowRight" && step < frame.total - 1)
        onStep(step + 1);
      else if (event.key === "ArrowLeft" && step > 0) onStep(step - 1);
      else if (event.key === "Escape") onExit();
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, frame.total, onStep, onExit]);

  return (
    <aside
      className="guide-bar"
      role="region"
      aria-label={t("region")}
      data-testid="guide-bar"
    >
      <div className="guide-bubble" aria-live="polite">
        {frame.narration && (
          <p data-testid="guide-narration">{frame.narration}</p>
        )}
        {evidence &&
          (evidence.found ? (
            <p className="guide-evidence" data-testid="guide-evidence">
              {evidence.path
                ? t("evidence", {
                    path: evidence.path,
                    value: preview(evidence.value),
                  })
                : evidence.text}
            </p>
          ) : (
            <p className="guide-missing" data-testid="guide-missing">
              {t("missing", { text: evidence.text })}
            </p>
          ))}
      </div>
      <div className="guide-controls">
        <Button
          size="sm"
          variant="ghost"
          disabled={step === 0}
          onClick={() => onStep(step - 1)}
        >
          <ChevronLeft size={15} aria-hidden="true" />
          {t("prev")}
        </Button>
        <span>{t("position", { current: step + 1, total: frame.total })}</span>
        <Button
          size="sm"
          disabled={step >= frame.total - 1}
          data-testid="guide-next"
          onClick={() => onStep(step + 1)}
        >
          {t("next")}
          <ChevronRight size={15} aria-hidden="true" />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={t("exit")}
          onClick={onExit}
        >
          <X size={15} aria-hidden="true" />
        </Button>
      </div>
    </aside>
  );
}
