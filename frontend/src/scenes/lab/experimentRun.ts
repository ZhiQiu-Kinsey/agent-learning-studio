import type { Experiment } from "../../content/types.gen";
import type { Detail, Trace } from "../../types";

type Exercise = Detail["exercises"][number];

/**
 * Whether the learner can run this arm from the page. Fault-injection presets
 * (`offline_only`) run only in automated tests; the server refuses them live.
 */
export function armRunnable(
  exerciseId: string,
  exercises: readonly Exercise[],
) {
  const exercise = exercises.find((item) => item.id === exerciseId);
  return !!exercise && !exercise.offline_only;
}

/** The first experiment that lists the exercise as one of its arms. */
export function experimentOf(
  experiments: readonly Experiment[],
  exerciseId: string,
): Experiment | undefined {
  return experiments.find((experiment) =>
    experiment.arms.some((arm) => arm.exercise === exerciseId),
  );
}

/**
 * The exercise to select after switching to `experiment`: the current one if it
 * is already an arm, otherwise the first arm the learner can run. Returns null
 * when nothing should change (no runnable arm, or already on one).
 */
export function exerciseForExperiment(
  experiment: Experiment,
  exercises: readonly Exercise[],
  current: string,
): string | null {
  if (experiment.arms.some((arm) => arm.exercise === current)) return null;
  const arm = experiment.arms.find((item) =>
    armRunnable(item.exercise, exercises),
  );
  return arm ? arm.exercise : null;
}

/**
 * Only a run of one of this experiment's arms is its evidence. A run of another
 * experiment stays on the stage, but its observe points read "not run yet"
 * instead of being checked against the wrong run.
 */
export function evidenceEvents(
  experiment: Experiment,
  runExerciseId: string,
  events: readonly Trace[],
): readonly Trace[] {
  return runExerciseId &&
    experiment.arms.some((arm) => arm.exercise === runExerciseId)
    ? events
    : [];
}
