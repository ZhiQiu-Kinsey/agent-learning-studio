import { describe, expect, it } from "vitest";
import type { Experiment } from "../../../content/types.gen";
import type { Detail, Trace } from "../../../types";
import {
  armRunnable,
  evidenceEvents,
  exerciseForExperiment,
  experimentOf,
} from "../experimentRun";

const exercises = [
  { id: "chain", title: "chain", question: "q" },
  { id: "both", title: "both", question: "q" },
  { id: "unknown", title: "unknown", question: "q", offline_only: true },
  { id: "malformed", title: "malformed", question: "q", offline_only: true },
] as Detail["exercises"];

const experiment = (id: string, arms: string[]): Experiment => ({
  id,
  title: id,
  hypothesis: null,
  predict: null,
  arms: arms.map((exercise) => ({
    id: exercise,
    exercise,
    label: null,
    inputs: null,
  })) as Experiment["arms"],
  observe: [],
  guide: [],
  conclusion: null,
});
const dependency = experiment("dependency", ["chain"]);
const independent = experiment("independent", ["both"]);
const injected = experiment("injected", ["unknown", "malformed"]);
const run = [{ type: "run_start" }, { type: "done" }] as Trace[];

describe("experiment arms and the exercise to run", () => {
  it("only lets the learner run arms the server accepts live", () => {
    expect(armRunnable("chain", exercises)).toBe(true);
    expect(armRunnable("unknown", exercises)).toBe(false);
    expect(armRunnable("missing", exercises)).toBe(false);
  });

  it("finds the experiment an exercise belongs to", () => {
    const all = [dependency, independent, injected];
    expect(experimentOf(all, "both")?.id).toBe("independent");
    expect(experimentOf(all, "nope")).toBeUndefined();
  });

  it("switches to the new experiment's first runnable arm", () => {
    expect(exerciseForExperiment(independent, exercises, "chain")).toBe("both");
    // Already on one of its arms: nothing to change.
    expect(exerciseForExperiment(dependency, exercises, "chain")).toBeNull();
    // Fault injection only: keep the current exercise rather than pick one that cannot run.
    expect(exerciseForExperiment(injected, exercises, "chain")).toBeNull();
  });
});

describe("which run counts as an experiment's evidence", () => {
  it("is the run of one of its own arms", () => {
    expect(evidenceEvents(dependency, "chain", run)).toBe(run);
  });

  it("is nothing for another experiment's run or before any run", () => {
    expect(evidenceEvents(independent, "chain", run)).toEqual([]);
    expect(evidenceEvents(dependency, "", run)).toEqual([]);
  });
});
