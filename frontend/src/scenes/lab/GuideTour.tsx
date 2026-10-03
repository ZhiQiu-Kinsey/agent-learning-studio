import { useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { StudioState } from "../../hooks/useStudio";
import type { GuideFrame } from "../../content/guide";
import type { Experiment } from "../../content/types.gen";
import BlurText from "../../components/react-bits/BlurText";
import type { EvidenceFocus } from "../../components/workspace/lab/evidenceFocus";
import Tour from "../../tour/Tour";
import type { TourStep, TourTarget } from "../../tour/types";
import type { NodeRole } from "../../stage/derive";
import { guidePlan, type GuideAim } from "./guidePlan";
import { locateEvent } from "./locate";

const frames = (count: number) =>
  new Promise<void>((resolve) => {
    const tick = (left: number) =>
      left ? requestAnimationFrame(() => tick(left - 1)) : resolve();
    tick(count);
  });

const query = (selector: string) =>
  document.querySelector<HTMLElement>(selector);

/**
 * The page element a step frames. Evidence falls back to its event row; a stage
 * role this run has no node for falls back to the whole stage. Never unrelated UI.
 */
function targetFor(aim: GuideAim): TourTarget {
  if (aim.kind === "center") return { kind: "center" };
  if (aim.kind === "stage")
    return {
      kind: "element",
      find: () =>
        query(
          `[data-testid="lab-workspace"] .stage-node[data-role="${aim.role}"]`,
        ) ?? query('[data-testid="lab-workspace"] [data-testid="agent-stage"]'),
    };
  const row = `[data-testid="lab-workspace"] [data-event-index="${aim.index}"]`;
  const find = () =>
    (aim.report ? query("[data-evidence-board]") : null) ??
    query("[data-evidence-mark]") ??
    query(row);
  return {
    kind: "element",
    find,
    // A field taller than its code box is framed by the box itself.
    frame: () => {
      const element = find();
      const box = element?.closest("pre");
      return element && box && element.offsetHeight > box.clientHeight
        ? box
        : element;
    },
  };
}

/** A short, literal rendering of the evidence value; arrays and objects only report their size. */
function preview(
  value: unknown,
  sized: {
    items: (count: number) => string;
    fields: (count: number) => string;
  },
) {
  if (Array.isArray(value)) return sized.items(value.length);
  if (value && typeof value === "object")
    return sized.fields(Object.keys(value).length);
  const text = JSON.stringify(value) ?? String(value);
  return text.length > 72 ? `${text.slice(0, 71)}…` : text;
}

function StepBody({
  frame,
  events,
}: {
  frame: GuideFrame;
  events: StudioState["events"];
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab.guide" });
  const evidence = frame.evidence;
  return (
    <>
      <p className="tour-text" data-testid="guide-narration">
        <BlurText text={frame.text} delay={14} />
      </p>
      {evidence &&
        (evidence.found ? (
          // Run data: shown as recorded, no effects.
          <p className="tour-evidence" data-testid="guide-evidence">
            <span>{t("evidenceAt", { index: evidence.index + 1 })}</span>
            <code>
              {[events[evidence.index]?.type, evidence.path]
                .filter(Boolean)
                .join(" · ")}
            </code>
            {evidence.path && (
              <span className="tour-evidence-value">
                {preview(evidence.value, {
                  items: (count) => t("items", { count }),
                  fields: (count) => t("fields", { count }),
                })}
              </span>
            )}
          </p>
        ) : (
          <p className="tour-missing" data-testid="guide-missing">
            {t("missing", { text: evidence.text })}
          </p>
        ))}
    </>
  );
}

/**
 * Guided replay over the learner's own run as a masked tour: each step frames
 * the evidence its sentence talks about (the event's field in the inspector,
 * the evidence board, or a stage node). Lazy-loaded with the tour.
 */
export default function GuideTour({
  experiment,
  studio,
  step,
  onStep,
  onExit,
  onFocus,
  onSpotlight,
}: {
  experiment: Experiment;
  studio: StudioState;
  step: number;
  onStep: (step: number) => void;
  onExit: (finished: boolean) => void;
  onFocus: (focus: EvidenceFocus | null) => void;
  onSpotlight: (role: string | null) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab.guide" });
  const { t: ts } = useTranslation("stage");
  // Steps must stay stable while the studio re-renders; actions read the latest.
  const latest = useRef({ studio, onFocus, onSpotlight });
  latest.current = { studio, onFocus, onSpotlight };
  const plan = useMemo(
    () => guidePlan(experiment, studio.events),
    [experiment, studio.events],
  );
  const steps = useMemo<TourStep[]>(
    () =>
      plan.map(({ id, frame, aim }) => ({
        id,
        target: targetFor(aim),
        prepare: async () => {
          const { studio, onFocus, onSpotlight } = latest.current;
          onSpotlight(frame.stage);
          if (aim.kind === "evidence") {
            onFocus({ index: aim.index, path: aim.path, reveal: false });
            locateEvent(studio, aim.index);
          }
          await frames(2);
        },
        badge: frame.stage ? (
          <span className="tour-badge" data-role={frame.stage}>
            {ts(`role.${frame.stage as NodeRole}`)}
          </span>
        ) : null,
        body: <StepBody frame={frame} events={studio.events} />,
      })),
    // studio.events is part of plan; ts is stable per language.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [plan, ts],
  );
  return (
    <Tour
      steps={steps}
      index={step}
      label={t("region")}
      onIndex={onStep}
      onExit={onExit}
    />
  );
}
