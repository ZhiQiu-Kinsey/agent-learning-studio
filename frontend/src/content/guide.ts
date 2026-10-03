import type { Trace } from "../types";
import { findEvidence } from "./selector";
import type { Experiment } from "./types.gen";

export type GuideFrame = {
  step: number;
  total: number;
  /** The sentence for this step. */
  text: string;
  /** Stage node role the step is about (model / runtime / tool / memory / user). */
  stage: string | null;
  /** Evidence the step points at, resolved against the learner's own run. */
  evidence:
    | {
        observe: string;
        text: string;
        found: true;
        index: number;
        value: unknown;
        path: string | null;
      }
    | { observe: string; text: string; found: false }
    | null;
};

/**
 * Resolves one step of a guided replay over the learner's real run: its
 * sentence, the stage role it is about, and the evidence it points at. Missing
 * evidence is reported as such; the guide never points elsewhere.
 */
export function resolveGuide(
  experiment: Experiment,
  events: readonly Trace[],
  step: number,
): GuideFrame {
  const steps = experiment.guide;
  const current = Math.max(0, Math.min(step, steps.length - 1));
  const item = steps[current];
  const frame: GuideFrame = {
    step: current,
    total: steps.length,
    text: item?.text ?? "",
    stage: item?.stage ?? null,
    evidence: null,
  };
  const point = item?.observe
    ? experiment.observe.find((candidate) => candidate.id === item.observe)
    : undefined;
  if (point) {
    const result = point.selector
      ? findEvidence(point.selector, events)
      : { found: false as const };
    frame.evidence = result.found
      ? {
          observe: point.id,
          text: point.text,
          found: true,
          index: result.index,
          value: result.value,
          path: point.selector?.path ?? null,
        }
      : { observe: point.id, text: point.text, found: false };
  }
  return frame;
}

export type ObserveStatus =
  | { id: string; text: string; status: "no-run" }
  | { id: string; text: string; status: "found"; index: number }
  | { id: string; text: string; status: "missing" }
  /** A plain-text hint without a selector: the learner checks it by reading. */
  | { id: string; text: string; status: "manual" };

/** Evidence status of every observe point against the learner's current run. */
export function observeStatus(
  experiment: Experiment,
  events: readonly Trace[],
): ObserveStatus[] {
  return experiment.observe.map((point) => {
    if (!point.selector)
      return { id: point.id, text: point.text, status: "manual" };
    if (!events.length)
      return { id: point.id, text: point.text, status: "no-run" };
    const result = point.selector
      ? findEvidence(point.selector, events)
      : { found: false as const };
    return result.found
      ? { id: point.id, text: point.text, status: "found", index: result.index }
      : { id: point.id, text: point.text, status: "missing" };
  });
}
