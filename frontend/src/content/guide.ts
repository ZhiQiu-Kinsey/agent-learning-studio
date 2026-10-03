import type { Trace } from "../types";
import { findEvidence } from "./selector";
import type { Experiment } from "./types.gen";

export type GuideFrame = {
  step: number;
  total: number;
  /** Latest narration at or before this step. */
  narration: string | null;
  /** Stage node role to spotlight (model / runtime / tool / memory / user). */
  spotlight: string | null;
  /** Evidence the step points at, resolved against the learner's own run. */
  evidence:
    | {
        observe: string;
        text: string;
        found: true;
        index: number;
        value: unknown;
        highlight: boolean;
        path: string | null;
      }
    | { observe: string; text: string; found: false }
    | null;
};

/**
 * Where each learner-facing step ends in the authored action list. A step is
 * one sentence: the spotlight / seek / highlight actions before a narration
 * set up the evidence that sentence talks about, so a step stops at each
 * narration. Actions after the last narration form one more step.
 */
export function guideStops(experiment: Experiment): number[] {
  const actions = experiment.guide;
  const stops = actions.flatMap((action, index) =>
    action.action === "narrate" ? [index] : [],
  );
  if (actions.length && stops.at(-1) !== actions.length - 1)
    stops.push(actions.length - 1);
  return stops;
}

/**
 * Resolves the state of a guided replay at `step` (one sentence each) over the
 * learner's real run. Jumping straight to a step re-applies the most recent
 * narration, spotlight and evidence before it, so the view is the same as
 * reaching it step by step. Missing evidence is reported as such; the guide
 * never points elsewhere.
 */
export function resolveGuide(
  experiment: Experiment,
  events: readonly Trace[],
  step: number,
): GuideFrame {
  const actions = experiment.guide;
  const stops = guideStops(experiment);
  const current = Math.max(0, Math.min(step, stops.length - 1));
  const at = stops[current] ?? -1;
  const frame: GuideFrame = {
    step: current,
    total: stops.length,
    narration: null,
    spotlight: null,
    evidence: null,
  };
  for (let index = 0; index <= at; index++) {
    const action = actions[index];
    if (action.action === "narrate") frame.narration = action.text;
    else if (action.action === "spotlight") frame.spotlight = action.target;
    else {
      const point = experiment.observe.find(
        (item) => item.id === action.observe,
      );
      if (!point) continue;
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
            highlight: action.action === "highlight",
            path: point.selector?.path ?? null,
          }
        : { observe: point.id, text: point.text, found: false };
    }
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
