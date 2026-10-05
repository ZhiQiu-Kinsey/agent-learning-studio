import type { Trace } from "../types";
import type { Arm, CountEvents, Experiment, Predict } from "./types.gen";

/**
 * The arm a prediction is about: the one the block names, or the experiment's
 * only arm. Null when the experiment is missing or the arm cannot be told
 * (the content schema rejects a multi-arm experiment without `arm`).
 */
export function predictArm(
  block: Pick<Predict, "experiment" | "arm">,
  experiments: readonly Experiment[],
): Arm | null {
  const experiment = experiments.find((item) => item.id === block.experiment);
  if (!experiment) return null;
  if (block.arm)
    return experiment.arms.find((arm) => arm.id === block.arm) ?? null;
  return experiment.arms.length === 1 ? experiment.arms[0] : null;
}

/**
 * Only a run of the predicted arm's exercise answers the prediction. Events of
 * another exercise (the other arm, say) stay on stage but count as "not run".
 */
export function predictEvents(
  exerciseId: string | null | undefined,
  runExerciseId: string,
  events: readonly Trace[],
): readonly Trace[] {
  return exerciseId && runExerciseId === exerciseId ? events : [];
}

/** Tool name as it appears on real tool events (call payload or result). */
function toolName(event: Trace): string | undefined {
  const data = event.data;
  const fn = data.function;
  if (
    fn &&
    typeof fn === "object" &&
    "name" in fn &&
    typeof fn.name === "string"
  )
    return fn.name;
  return typeof data.name === "string" ? data.name : undefined;
}

export type PredictOutcome =
  | { status: "no-run" }
  | { status: "computed"; actual: number; matches: boolean | null };

/**
 * Compares a learner's prediction with a fact computed from real events only.
 * Without a run there is nothing to compare; illustrations and recordings are
 * excluded so a prediction is never "confirmed" by data the learner did not produce.
 */
export function evaluatePredict(
  rule: CountEvents,
  events: readonly Trace[],
  prediction?: number,
): PredictOutcome {
  const real = events.filter(
    (event) => !event.provenance || event.provenance === "real_run",
  );
  if (!real.length) return { status: "no-run" };
  const actual = real.filter(
    (event) =>
      event.type === rule.event &&
      (!rule.name || toolName(event) === rule.name),
  ).length;
  return {
    status: "computed",
    actual,
    matches: prediction === undefined ? null : prediction === actual,
  };
}
