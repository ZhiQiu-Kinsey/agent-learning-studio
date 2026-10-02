import { useTranslation } from "react-i18next";
import { Crosshair } from "lucide-react";
import type { StudioState } from "../../hooks/useStudio";
import { observeStatus } from "../../content/guide";
import type { Experiment } from "../../content/types.gen";
import { Button } from "../../components/ui/button";
import RubberSegment from "../../components/react-bits/RubberSegment";

/**
 * Experiment card: hypothesis, arms (each an exercise of this lesson) and
 * observe points checked against the learner's own run.
 */
export function ExperimentPanel({
  experiments,
  selected,
  onSelect,
  studio,
}: {
  experiments: Experiment[];
  selected: Experiment;
  onSelect: (id: string) => void;
  studio: StudioState;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab" });
  const statuses = observeStatus(selected, studio.events);
  const exercises = studio.detail?.exercises ?? [];
  return (
    <section
      className="experiment-panel"
      aria-label={t("experiments")}
      data-testid="experiment-panel"
    >
      {experiments.length > 1 && (
        <RubberSegment
          aria-label={t("experiments")}
          size="sm"
          items={experiments.map((item) => ({
            value: item.id,
            label: item.title,
          }))}
          value={selected.id}
          onChange={onSelect}
          disabled={studio.running}
          trackColor="var(--surface-muted)"
          thumbColor="var(--surface)"
          textColor="var(--text-muted)"
          activeTextColor="var(--text)"
        />
      )}
      <h3>{selected.title}</h3>
      {selected.hypothesis && (
        <p className="experiment-hypothesis">
          <strong>{t("hypothesis")}</strong>
          {selected.hypothesis}
        </p>
      )}
      {selected.arms.length > 0 && (
        <div className="experiment-arms">
          <span>{t("arms")}</span>
          <div>
            {selected.arms.map((arm) => {
              const exercise = exercises.find(
                (item) => item.id === arm.exercise,
              );
              if (!exercise) return null;
              return (
                <Button
                  key={arm.id}
                  size="sm"
                  variant={
                    studio.exerciseId === arm.exercise ? "default" : "outline"
                  }
                  aria-pressed={studio.exerciseId === arm.exercise}
                  disabled={studio.running}
                  data-testid={`experiment-arm-${arm.id}`}
                  onClick={() => studio.selectExercise(arm.exercise)}
                >
                  {arm.label ?? exercise.title}
                </Button>
              );
            })}
          </div>
        </div>
      )}
      {statuses.length > 0 && (
        <div className="experiment-observe">
          <span>{t("observe")}</span>
          <ol>
            {statuses.map((point) => (
              <li
                key={point.id}
                data-status={point.status}
                data-testid="experiment-observe"
              >
                <span>{point.text}</span>
                <small>
                  {point.status === "found"
                    ? t("status.found", { index: point.index + 1 })
                    : t(`status.${point.status}`)}
                </small>
                {point.status === "found" && (
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`${t("locate")} ${point.text}`}
                    onClick={() => {
                      studio.seek(point.index + 1);
                      studio.selectEvent(point.index);
                    }}
                  >
                    <Crosshair size={14} aria-hidden="true" />
                    {t("locate")}
                  </Button>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
