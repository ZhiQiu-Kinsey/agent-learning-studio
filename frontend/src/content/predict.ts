import type { Trace } from "../types";
import type { CountEvents } from "./types.gen";

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
