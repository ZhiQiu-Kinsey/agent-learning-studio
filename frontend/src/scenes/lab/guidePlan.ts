import type { Trace } from "../../types";
import { resolveGuide, type GuideFrame } from "../../content/guide";
import type { Experiment } from "../../content/types.gen";

/** Where one guide step frames, decided from the learner's own run. */
export type GuideAim =
  /** A real event (and optionally a field inside it, selector path relative to the event). */
  | { kind: "evidence"; index: number; path: string | null; report: boolean }
  /** A stage node of the run. */
  | { kind: "stage"; role: string }
  /** Nothing to frame: an opening line, or evidence this run did not produce. */
  | { kind: "center" };

export type GuidePlanStep = { id: string; frame: GuideFrame; aim: GuideAim };

/**
 * Plans the masked guide over the learner's run: each step's sentence and what
 * to frame. Evidence that this run did not produce is never replaced by
 * something else; the step is shown in the middle and says so.
 */
export function guidePlan(
  experiment: Experiment,
  events: readonly Trace[],
): GuidePlanStep[] {
  return experiment.guide.map((_, step) => {
    const frame = resolveGuide(experiment, events, step);
    const evidence = frame.evidence;
    const aim: GuideAim = evidence
      ? evidence.found
        ? {
            kind: "evidence",
            index: evidence.index,
            path: evidence.path,
            report: events[evidence.index]?.type === "lesson.report",
          }
        : { kind: "center" }
      : frame.stage
        ? { kind: "stage", role: frame.stage }
        : { kind: "center" };
    return { id: `${experiment.id}-${step}`, frame, aim };
  });
}
