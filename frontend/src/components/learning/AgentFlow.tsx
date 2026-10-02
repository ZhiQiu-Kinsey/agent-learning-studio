import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useReducedMotion } from "../../motion";
import {
  ArrowLeft,
  ArrowRight,
  CheckCheck,
  Code2,
  CornerDownRight,
  Info,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Walkthrough } from "../../content/types.gen";
import { Code } from "../Code";
import { GlossaryText } from "../../content/glossary/Glossary";
import Shuffle from "../react-bits/Shuffle";

const ease = [0.16, 1, 0.3, 1] as const;

/**
 * Teaching walkthrough (illustration, never a run record). Stepper-style: the
 * progress rail fills as the learner moves; nothing advances by itself.
 */
export function AgentFlow({ flow }: { flow: Walkthrough }) {
  const { t } = useTranslation();
  const { t: tw } = useTranslation("blocks", { keyPrefix: "walkthrough" });
  const [selected, setSelected] = useState(0);
  const [direction, setDirection] = useState(1);
  const reduced = useReducedMotion();
  const step = flow.steps[selected];
  if (!step) return null;
  const select = (index: number) => {
    setDirection(index >= selected ? 1 : -1);
    setSelected(index);
  };
  const progress =
    flow.steps.length > 1 ? selected / (flow.steps.length - 1) : 1;
  return (
    <section
      className="agent-flow"
      id="lesson-flow"
      aria-label={tw("region")}
      data-testid="agent-flow"
    >
      <div className="learn-section-kicker">
        <Shuffle text={tw("kicker")} />
        <span
          className="lesson-example-tag"
          data-testid="agent-flow-provenance"
        >
          <Info size={12} />
          {t("provenance.illustration")}
        </span>
      </div>
      <div className="agent-flow-heading">
        <h2>{flow.title}</h2>
        {flow.description && <p>{flow.description}</p>}
      </div>
      <div className="agent-flow-stepper">
        <div className="agent-flow-steps" aria-label={tw("steps")}>
          {flow.steps.map((item, index) => (
            <button
              key={item.id}
              className={`agent-flow-step ${index === selected ? "is-selected" : ""} ${index < selected ? "is-visited" : ""}`}
              data-testid="agent-flow-step"
              onClick={() => select(index)}
              aria-pressed={index === selected}
              aria-controls="agent-flow-detail"
            >
              <motion.span
                className="agent-step-number"
                animate={
                  reduced ? undefined : { scale: index === selected ? 1.12 : 1 }
                }
                transition={{ type: "spring", bounce: 0.5, duration: 0.45 }}
              >
                {index < selected ? <CheckCheck size={14} /> : `0${index + 1}`}
              </motion.span>
              <span>
                <strong>{item.label}</strong>
                <small>{item.actor}</small>
              </span>
              {index < flow.steps.length - 1 && (
                <ArrowRight
                  className="agent-step-connector"
                  size={14}
                  aria-hidden="true"
                />
              )}
            </button>
          ))}
        </div>
        <div
          className="agent-flow-rail"
          role="progressbar"
          aria-label={tw("progress")}
          aria-valuemin={1}
          aria-valuemax={flow.steps.length}
          aria-valuenow={selected + 1}
        >
          <motion.span
            className="agent-flow-rail-fill"
            initial={false}
            animate={{ scaleX: progress }}
            transition={
              reduced
                ? { duration: 0 }
                : { type: "spring", bounce: 0.2, duration: 0.6 }
            }
          />
        </div>
      </div>
      <AnimatePresence mode="wait" initial={false} custom={direction}>
        <motion.div
          key={selected}
          id="agent-flow-detail"
          className="agent-flow-detail"
          aria-live="polite"
          initial={
            reduced
              ? false
              : { opacity: 0, x: 24 * direction, filter: "blur(6px)" }
          }
          animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
          exit={
            reduced
              ? undefined
              : { opacity: 0, x: -16 * direction, filter: "blur(4px)" }
          }
          transition={{ duration: 0.28, ease }}
        >
          <div
            className="agent-flow-explanation"
            data-testid="agent-flow-explanation"
          >
            <span className="agent-flow-actor">
              <CornerDownRight size={15} />
              {step.actor}
            </span>
            <h3>{step.title}</h3>
            <p>
              <GlossaryText text={step.body} />
            </p>
            {step.evidence && (
              <div className="agent-flow-evidence">
                <span className="agent-evidence-icon">
                  <CheckCheck size={17} />
                </span>
                <div>
                  <strong>{tw("evidence")}</strong>
                  <p>{step.evidence}</p>
                </div>
              </div>
            )}
          </div>
          {step.code && (
            <div className="agent-flow-code" data-testid="agent-flow-code">
              <div className="agent-code-toolbar">
                <span>
                  <Code2 size={13} />
                  {step.language === "python" ? tw("python") : tw("messages")}
                </span>
                <span>{tw("snippet")}</span>
              </div>
              <Code content={step.code} language={step.language} />
            </div>
          )}
        </motion.div>
      </AnimatePresence>
      <div className="agent-flow-footer">
        <p>{tw("hint")}</p>
        <div>
          <span>
            {String(selected + 1).padStart(2, "0")}
            <i> / {String(flow.steps.length).padStart(2, "0")}</i>
          </span>
          <button
            aria-label={tw("prev")}
            disabled={selected === 0}
            onClick={() => select(selected - 1)}
          >
            <ArrowLeft size={15} />
          </button>
          <button
            aria-label={tw("next")}
            disabled={selected === flow.steps.length - 1}
            onClick={() => select(selected + 1)}
          >
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </section>
  );
}
