import { useTranslation } from "react-i18next";
import {
  CircleAlert,
  CircleCheck,
  Clock3,
  Crosshair,
  Eye,
  FlaskConical,
  Check,
} from "lucide-react";
import type { StudioState } from "../../hooks/useStudio";
import { observeStatus, type ObserveStatus } from "../../content/guide";
import type { Experiment } from "../../content/types.gen";
import { GlossaryText } from "../../content/glossary/Glossary";
import RubberSegment from "../../components/react-bits/RubberSegment";
import { segmentColors } from "../../components/lab/controlColors";

const statusIcon = {
  "no-run": Clock3,
  found: CircleCheck,
  missing: CircleAlert,
  manual: Eye,
} as const;

const two = (value: number) => String(value).padStart(2, "0");

/** One status pill per observe point: same shape, colour and icon by status. */
function StatusPill({ point }: { point: ObserveStatus }) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab" });
  const Icon = statusIcon[point.status];
  return (
    <small className="experiment-status" data-status={point.status}>
      <Icon size={13} aria-hidden="true" />
      {point.status === "found"
        ? t("status.found", { index: point.index + 1 })
        : t(`status.${point.status}`)}
    </small>
  );
}

/**
 * Experiment card: hypothesis, arms (each an exercise of this lesson) and
 * observe points checked against the learner's own run.
 */
export function ExperimentPanel({
  experiments,
  selected,
  onSelect,
  onLocate,
  studio,
}: {
  experiments: Experiment[];
  selected: Experiment;
  onSelect: (id: string) => void;
  /** Point the lab at an observe point's evidence: the event and its field. */
  onLocate: (index: number, path: string | null) => void;
  studio: StudioState;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab" });
  const statuses = observeStatus(selected, studio.events);
  const exercises = studio.detail?.exercises ?? [];
  const position = Math.max(
    0,
    experiments.findIndex((item) => item.id === selected.id),
  );
  return (
    <section
      className="experiment-panel"
      aria-label={t("experiments")}
      data-testid="experiment-panel"
    >
      <header className="experiment-head">
        <span className="experiment-eyebrow">
          <FlaskConical size={14} aria-hidden="true" />
          {t("eyebrow")}
          {experiments.length > 1 && (
            <span className="experiment-counter">
              {t("counter", {
                current: two(position + 1),
                total: two(experiments.length),
              })}
            </span>
          )}
        </span>
        {experiments.length > 1 && (
          <div className="experiment-switch">
            <RubberSegment
              aria-label={t("experiments")}
              size="sm"
              items={experiments.map((item, index) => ({
                value: item.id,
                label: t("experimentTab", { number: index + 1 }),
              }))}
              value={selected.id}
              onChange={onSelect}
              disabled={studio.running}
              {...segmentColors}
            />
          </div>
        )}
      </header>
      <h3 className="experiment-title">{selected.title}</h3>
      {selected.hypothesis && (
        <blockquote className="experiment-hypothesis">
          <strong>{t("hypothesis")}</strong>
          <p>
            <GlossaryText text={selected.hypothesis} />
          </p>
        </blockquote>
      )}
      {selected.arms.length > 0 && (
        <div className="experiment-arms">
          <span className="experiment-label">{t("arms")}</span>
          <div className="experiment-arm-list">
            {selected.arms.map((arm, index) => {
              const exercise = exercises.find(
                (item) => item.id === arm.exercise,
              );
              if (!exercise) return null;
              const pressed = studio.exerciseId === arm.exercise;
              return (
                <button
                  key={arm.id}
                  type="button"
                  className="experiment-arm"
                  aria-pressed={pressed}
                  disabled={studio.running}
                  data-testid={`experiment-arm-${arm.id}`}
                  onClick={() => studio.selectExercise(arm.exercise)}
                >
                  <span className="experiment-arm-key" aria-hidden="true">
                    {String.fromCharCode(65 + index)}
                  </span>
                  <span className="experiment-arm-text">
                    {arm.label ?? exercise.title}
                  </span>
                  <span className="experiment-arm-check" aria-hidden="true">
                    <Check size={13} strokeWidth={3} />
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
      {statuses.length > 0 && (
        <div className="experiment-observe">
          <span className="experiment-label">{t("observe")}</span>
          <ol>
            {statuses.map((point, index) => (
              <li
                key={point.id}
                data-status={point.status}
                data-testid="experiment-observe"
              >
                <span className="experiment-observe-index" aria-hidden="true">
                  {two(index + 1)}
                </span>
                <span className="experiment-observe-text">
                  <GlossaryText text={point.text} />
                </span>
                <StatusPill point={point} />
                <span className="experiment-observe-action">
                  {point.status === "found" && (
                    <button
                      type="button"
                      className="experiment-locate"
                      aria-label={`${t("locate")} ${point.text}`}
                      onClick={() =>
                        onLocate(
                          point.index,
                          selected.observe.find((item) => item.id === point.id)
                            ?.selector?.path ?? null,
                        )
                      }
                    >
                      <Crosshair size={13} aria-hidden="true" />
                      {t("locate")}
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
