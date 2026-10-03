import { createContext, useContext, useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Check, X } from "lucide-react";
import { motion } from "motion/react";
import {
  EVENTS,
  Joyride,
  type ArrowRenderProps,
  type EventData,
  type Step,
  type TooltipRenderProps,
} from "react-joyride";
import { useReducedMotion } from "../motion";
import SpotlightCard from "../components/react-bits/SpotlightCard";
import { Button } from "../components/ui/button";
import { reveal } from "./reveal";
import type { TourStep } from "./types";
import "./tour.css";

type TourControls = {
  label: string;
  onIndex: (index: number) => void;
  onExit: (finished: boolean) => void;
};

const TourContext = createContext<TourControls | null>(null);

/** Typing in a field or dragging a slider never moves the tour. */
const isEditable = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  !!target.closest(
    "input, textarea, select, [contenteditable='true'], [role='slider']",
  );

/**
 * Joyride sizes the arrow's box per side but does not rotate a custom arrow,
 * so each side gets its own triangle (same geometry as Joyride's built-in one):
 * the tip always points at the framed element.
 */
function TourArrow({ base, size, placement }: ArrowRenderProps) {
  const side = placement.split("-")[0];
  const vertical = side === "left" || side === "right";
  const [width, height] = vertical ? [size, base] : [base, size];
  const points = {
    top: `0,0 ${base / 2},${size} ${base},0`,
    bottom: `${base},${size} ${base / 2},0 0,${size}`,
    left: `0,0 ${size},${base / 2} 0,${base}`,
    right: `${size},${base} ${size},0 0,${base / 2}`,
  }[side];
  if (!points) return null;
  return (
    <svg
      className="tour-arrow"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
    >
      <polygon points={points} fill="currentColor" />
    </svg>
  );
}

/** Progress as one pill per step; the current one glides along. */
function TourProgress({ index, total }: { index: number; total: number }) {
  const reduced = useReducedMotion();
  return (
    <ol className="tour-progress" aria-hidden="true">
      {Array.from({ length: total }, (_, step) => (
        <li key={step} data-done={step < index || undefined}>
          {step === index && (
            <motion.span
              layoutId="tour-progress-current"
              className="tour-progress-current"
              transition={
                reduced
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 480, damping: 38 }
              }
            />
          )}
        </li>
      ))}
    </ol>
  );
}

function TourCard({
  step,
  index,
  size,
  isLastStep,
  tooltipProps,
}: TooltipRenderProps) {
  const { t } = useTranslation("common", { keyPrefix: "tour" });
  const controls = useContext(TourContext)!;
  const data = step.data as TourStep;
  const textId = `tour-text-${data.id}`;
  // Keyboard focus follows the step to "next". preventScroll matters: the card
  // may not be positioned yet, and a plain focus() would scroll to its old place.
  const next = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    next.current?.focus({ preventScroll: true });
  }, [index]);
  return (
    <div
      {...tooltipProps}
      aria-label={controls.label}
      aria-describedby={textId}
      className="tour-card-shell"
      data-testid="tour-card"
    >
      <SpotlightCard
        className="tour-card"
        spotlightColor="rgba(79, 209, 197, 0.14)"
      >
        <header className="tour-card-head">
          {data.badge}
          <span className="tour-position" data-testid="tour-position">
            {t("position", { current: index + 1, total: size })}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="tour-close"
            aria-label={t("exit")}
            onClick={() => controls.onExit(false)}
          >
            <X size={16} aria-hidden="true" />
          </Button>
        </header>
        <div className="tour-card-body" id={textId} key={data.id}>
          {data.body}
        </div>
        <footer className="tour-card-foot">
          <TourProgress index={index} total={size} />
          <div className="tour-card-actions">
            <Button
              variant="ghost"
              size="sm"
              disabled={index === 0}
              data-testid="tour-prev"
              onClick={() => controls.onIndex(index - 1)}
            >
              <ChevronLeft size={15} aria-hidden="true" />
              {t("prev")}
            </Button>
            <Button
              size="sm"
              ref={next}
              data-testid="tour-next"
              data-action="primary"
              onClick={() =>
                isLastStep ? controls.onExit(true) : controls.onIndex(index + 1)
              }
            >
              {isLastStep ? t("finish") : t("next")}
              {isLastStep ? (
                <Check size={15} aria-hidden="true" />
              ) : (
                <ChevronRight size={15} aria-hidden="true" />
              )}
            </Button>
          </div>
        </footer>
      </SpotlightCard>
    </div>
  );
}

/**
 * A masked, step-by-step tour (React Joyride, controlled). The page dims except
 * for one framed element; clicks on the dimmed area do nothing, the framed
 * element stays usable. ← / → move between steps, Esc leaves. Each step may
 * `prepare` the page (select data, switch views) before it is framed.
 * Reusable: it knows nothing about lessons or runs.
 */
export default function Tour({
  steps,
  index,
  label,
  onIndex,
  onExit,
}: {
  steps: TourStep[];
  index: number;
  /** Accessible name of the tour dialog. */
  label: string;
  onIndex: (index: number) => void;
  onExit: (finished: boolean) => void;
}) {
  const reduced = useReducedMotion();
  const controls = useMemo(
    () => ({ label, onIndex, onExit }),
    [label, onIndex, onExit],
  );
  // A step still preparing when the tour closes must not scroll the page afterwards.
  const open = useRef(true);
  useEffect(() => {
    open.current = true;
    return () => {
      open.current = false;
    };
  }, []);
  const joySteps = useMemo<Step[]>(
    () =>
      steps.map((step) => {
        const { target } = step;
        // Prepare the page, then scroll the target into place ourselves: the
        // frame is drawn once, where it ends up (Joyride's own scroll is off).
        const before = async () => {
          await step.prepare?.();
          if (!open.current || target.kind !== "element") return;
          const found = target.find();
          const frame = target.frame?.() ?? found;
          if (found && frame) await reveal(found, frame, !reduced);
        };
        return target.kind === "center"
          ? {
              id: step.id,
              target: "body",
              placement: "center",
              content: null,
              data: step,
              before,
            }
          : {
              id: step.id,
              target: target.find,
              spotlightTarget: target.frame,
              placement: "auto",
              content: null,
              data: step,
              before,
            };
      }),
    [steps, reduced],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      // A held arrow key must not race through every step (and count as finished).
      if (event.repeat || event.defaultPrevented) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isEditable(event.target)) return;
      if (event.key === "ArrowRight") {
        if (index < steps.length - 1) onIndex(index + 1);
        else onExit(true);
      } else if (event.key === "ArrowLeft") {
        if (index > 0) onIndex(index - 1);
      } else if (event.key === "Escape") onExit(false);
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, steps.length, onIndex, onExit]);

  return (
    <TourContext.Provider value={controls}>
      <Joyride
        run
        continuous
        steps={joySteps}
        stepIndex={index}
        tooltipComponent={TourCard}
        arrowComponent={TourArrow}
        loaderComponent={null}
        onEvent={(data: EventData) => {
          // Targets fall back to a container that always exists; if one is still
          // missing, move on rather than leave a dimmed page with no card.
          if (data.type !== EVENTS.TARGET_NOT_FOUND) return;
          if (data.index < steps.length - 1) onIndex(data.index + 1);
          else onExit(false);
        }}
        options={{
          // Strong mask: the dimmed page ignores clicks; Esc is handled above.
          overlayClickAction: false,
          dismissKeyAction: false,
          skipBeacon: true,
          skipScroll: true,
          blockTargetInteraction: false,
          overlayColor: "rgba(4, 7, 16, 0.74)",
          spotlightPadding: 8,
          spotlightRadius: 12,
          offset: 14,
          arrowBase: 22,
          arrowSize: 10,
          beforeTimeout: 4000,
          zIndex: 70,
        }}
        styles={{
          overlay: { backgroundColor: "rgba(4, 7, 16, 0.74)" },
          spotlight: { className: "tour-ring" },
        }}
      />
    </TourContext.Provider>
  );
}
