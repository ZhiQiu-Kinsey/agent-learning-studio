import { describe, expect, it } from "vitest";
import { migrate } from "../../lib/migrate";
import { emptyProgress, reduceProgress, type ProgressAction } from "../model";
import { createProgressStore } from "../store";

const at = "2026-10-01T12:00:00.000Z";
const later = "2026-10-01T12:05:00.000Z";
const run = (...actions: ProgressAction[]) =>
  actions.reduce(reduceProgress, emptyProgress());

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value);
    },
    removeItem: (key: string) => {
      data.delete(key);
    },
  };
}

describe("progress reducer", () => {
  it("records opens, first scene visits and the last lesson", () => {
    const state = run(
      { type: "lesson_opened", lessonId: "tool-selection", at },
      { type: "scene_visited", lessonId: "tool-selection", scene: "lab", at },
      { type: "scene_visited", lessonId: "tool-selection", scene: "lab", at: later },
      { type: "lesson_opened", lessonId: "tool-selection", at: later },
    );
    const lesson = state.lessons["tool-selection"];
    expect(lesson.firstOpenedAt).toBe(at);
    expect(lesson.lastOpenedAt).toBe(later);
    expect(lesson.scenes.lab).toBe(at);
    expect(state.lastLessonId).toBe("tool-selection");
  });

  it("counts each real run once, even if the same run is reported again", () => {
    const state = run(
      { type: "run_completed", lessonId: "a", runId: "r1", at },
      { type: "run_completed", lessonId: "a", runId: "r1", at: later },
      { type: "run_completed", lessonId: "a", runId: "r2", at: later },
    );
    expect(state.lessons.a.runs).toEqual({ count: 2, lastRunId: "r2", lastAt: later });
  });

  it("keeps the latest quiz score, counts attempts and rejects impossible scores", () => {
    const state = run(
      { type: "quiz_scored", lessonId: "a", correct: 1, total: 3, at },
      { type: "quiz_scored", lessonId: "a", correct: 3, total: 3, at: later },
      { type: "quiz_scored", lessonId: "a", correct: 4, total: 3, at: later },
    );
    expect(state.lessons.a.quiz).toEqual({ correct: 3, total: 3, at: later, attempts: 2 });
  });

  it("toggles checkpoints and keeps the first evidence per observe point", () => {
    const state = run(
      { type: "checkpoint_set", lessonId: "a", checkpointId: "c1", done: true, at },
      { type: "checkpoint_set", lessonId: "a", checkpointId: "c2", done: true, at },
      { type: "checkpoint_set", lessonId: "a", checkpointId: "c2", done: false, at },
      { type: "evidence_found", lessonId: "a", observeId: "o1", runId: "r1", at },
      { type: "evidence_found", lessonId: "a", observeId: "o1", runId: "r2", at: later },
    );
    expect(state.lessons.a.checkpoints).toEqual({ c1: at });
    expect(state.lessons.a.evidence).toEqual({ o1: { runId: "r1", at } });
  });

  it("renames alias ids without overwriting progress under the canonical id", () => {
    const state = run(
      { type: "lesson_opened", lessonId: "tool-selection", at: later },
      { type: "lesson_opened", lessonId: "3", at },
      { type: "lesson_opened", lessonId: "1", at },
      { type: "lessons_renamed", mapping: { "3": "tool-selection", "1": "first-call" } },
    );
    expect(Object.keys(state.lessons).sort()).toEqual(["first-call", "tool-selection"]);
    expect(state.lessons["tool-selection"].lastOpenedAt).toBe(later);
    expect(state.lastLessonId).toBe("first-call");
  });
});

describe("migration ladder", () => {
  const steps = [
    { from: 0, to: 1, up: () => ({ a: 1 }) },
    { from: 1, to: 2, up: (data: Record<string, unknown>) => ({ ...data, b: 2 }) },
  ];

  it("walks every step in order", () => {
    expect(migrate({}, 2, steps)).toEqual({
      status: "migrated",
      data: { a: 1, b: 2, version: 2 },
    });
    expect(migrate({ version: 2, a: 9 }, 2, steps)).toEqual({
      status: "current",
      data: { version: 2, a: 9 },
    });
  });

  it("fails on a missing step and leaves newer data alone", () => {
    expect(() => migrate({}, 2, [steps[1]])).toThrow("no migration from version 0");
    expect(migrate({ version: 5 }, 2, steps)).toEqual({ status: "newer", version: 5 });
  });
});

describe("progress store", () => {
  it("persists actions and clears storage", () => {
    const storage = memoryStorage();
    const store = createProgressStore(storage, "k");
    store.dispatch({ type: "lesson_opened", lessonId: "a", at });
    expect(JSON.parse(storage.data.get("k")!).lessons.a.firstOpenedAt).toBe(at);
    expect(createProgressStore(storage, "k").get().lastLessonId).toBe("a");
    store.dispatch({ type: "cleared" });
    expect(storage.data.has("k")).toBe(false);
  });

  it("never overwrites data written by a newer version or that it cannot read", () => {
    for (const original of [JSON.stringify({ version: 99, lessons: {} }), "{broken"]) {
      const storage = memoryStorage({ k: original });
      const store = createProgressStore(storage, "k");
      expect(store.writable).toBe(false);
      store.dispatch({ type: "lesson_opened", lessonId: "a", at });
      expect(store.get().lessons.a).toBeDefined();
      expect(storage.data.get("k")).toBe(original);
    }
  });
});
