import { describe, expect, it } from "vitest";
import { migrate } from "../../lib/migrate";
import {
  emptyProgress,
  huntEvidenceId,
  LEGACY_QUIZ_ID,
  PROGRESS_VERSION,
  progressMigrations,
  reduceProgress,
  RUN_ID_MEMORY,
  type ProgressAction,
  type ProgressRecord,
} from "../model";
import { createProgressStore } from "../store";
import { reviewNumbers } from "../summary";

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
      // 不相邻的重复上报（例如重连后再次报告 r1）同样不重复计数。
      { type: "run_completed", lessonId: "a", runId: "r1", at: later },
    );
    expect(state.lessons.a.runs).toEqual({
      count: 2,
      lastRunId: "r2",
      lastAt: later,
      seen: ["r1", "r2"],
    });
  });

  it("remembers a bounded number of run ids", () => {
    const actions = Array.from(
      { length: RUN_ID_MEMORY + 5 },
      (_, index): ProgressAction => ({
        type: "run_completed",
        lessonId: "a",
        runId: `r${index}`,
        at,
      }),
    );
    const runs = run(...actions).lessons.a.runs;
    expect(runs.count).toBe(RUN_ID_MEMORY + 5);
    expect(runs.seen).toHaveLength(RUN_ID_MEMORY);
    expect(runs.seen.at(-1)).toBe(`r${RUN_ID_MEMORY + 4}`);
  });

  it("keeps the latest score per quiz block with confidence, counts attempts and rejects impossible scores", () => {
    const answers = {
      q1: { correct: true, confidence: "high" as const },
      q2: { correct: false, confidence: "high" as const },
      q3: { correct: true, confidence: "low" as const },
    };
    const state = run(
      { type: "quiz_scored", lessonId: "a", quizId: "quiz", correct: 1, total: 3, at },
      { type: "quiz_scored", lessonId: "a", quizId: "quiz", correct: 2, total: 3, answers, at: later },
      // 越界、与明细不一致、未知信心档位都不会写入。
      { type: "quiz_scored", lessonId: "a", quizId: "quiz", correct: 4, total: 3, at: later },
      { type: "quiz_scored", lessonId: "a", quizId: "quiz", correct: 3, total: 3, answers, at: later },
      {
        type: "quiz_scored",
        lessonId: "a",
        quizId: "quiz",
        correct: 1,
        total: 1,
        answers: { q1: { correct: true, confidence: "sure" as never } },
        at: later,
      },
      { type: "quiz_scored", lessonId: "a", quizId: "other", correct: 1, total: 1, at: later },
    );
    expect(state.lessons.a.quizzes.quiz).toEqual({
      correct: 2,
      total: 3,
      at: later,
      attempts: 2,
      answers,
    });
    expect(state.lessons.a.quizzes.other).toMatchObject({ correct: 1, attempts: 1, answers: {} });
  });

  it("toggles checkpoints and keeps the first evidence per observe point", () => {
    const state = run(
      { type: "checkpoint_set", lessonId: "a", checkpointId: "c1", done: true, at },
      { type: "checkpoint_set", lessonId: "a", checkpointId: "c2", done: true, at },
      { type: "checkpoint_set", lessonId: "a", checkpointId: "c2", done: false, at },
      { type: "evidence_found", lessonId: "a", observeId: "o1", runId: "r1", at },
      { type: "evidence_found", lessonId: "a", observeId: "o1", runId: "r2", at: later },
      { type: "evidence_found", lessonId: "a", observeId: huntEvidenceId("hunt"), runId: "r2", seq: 8, at },
    );
    expect(state.lessons.a.checkpoints).toEqual({ c1: at });
    expect(state.lessons.a.evidence).toEqual({
      o1: { runId: "r1", at },
      "trace-hunt:hunt": { runId: "r2", at, seq: 8 },
    });
  });

  it("summarizes the review numbers from real records only", () => {
    expect(reviewNumbers(undefined)).toMatchObject({
      runs: 0,
      quizCorrect: 0,
      quizAttempts: 0,
      checkpoints: 0,
      evidence: 0,
      hasActivity: false,
    });
    const state = run(
      { type: "lesson_opened", lessonId: "a", at },
      { type: "scene_visited", lessonId: "a", scene: "review", at },
    );
    // 打开课程、访问场景不算学习动作，回顾页仍应显示空状态。
    expect(reviewNumbers(state.lessons.a).hasActivity).toBe(false);
    const busy = [
      { type: "run_completed", lessonId: "a", runId: "r1", at },
      { type: "run_completed", lessonId: "a", runId: "r1", at },
      {
        type: "quiz_scored",
        lessonId: "a",
        quizId: "quiz",
        correct: 1,
        total: 2,
        answers: { q1: { correct: true, confidence: "high" }, q2: { correct: false, confidence: "high" } },
        at,
      },
      { type: "checkpoint_set", lessonId: "a", checkpointId: "c/1", done: true, at },
      { type: "evidence_found", lessonId: "a", observeId: "trace-hunt:h", runId: "r1", at },
    ] satisfies ProgressAction[];
    const numbers = reviewNumbers(busy.reduce(reduceProgress, state).lessons.a);
    expect(numbers).toMatchObject({
      runs: 1,
      quizCorrect: 1,
      quizTotal: 2,
      quizAttempts: 1,
      checkpoints: 1,
      evidence: 1,
      hasActivity: true,
    });
    expect(numbers.confidence.high).toEqual({ answered: 2, correct: 1 });
    expect(numbers.confidence.low).toEqual({ answered: 0, correct: 0 });
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

describe("progress migrations", () => {
  // 第一版落在 localStorage 里的真实形状。
  const v1 = {
    version: 1,
    lastLessonId: "tool-selection",
    lessons: {
      "tool-selection": {
        firstOpenedAt: at,
        lastOpenedAt: later,
        scenes: { understand: at, check: later },
        runs: { count: 2, lastRunId: "r2", lastAt: later },
        quiz: { correct: 2, total: 3, at: later, attempts: 4 },
        checkpoints: { "quiz/1": at },
        evidence: { o1: { runId: "r1", at } },
      },
      "dependent-calls": {
        firstOpenedAt: at,
        lastOpenedAt: at,
        scenes: {},
        runs: { count: 0 },
        checkpoints: {},
        evidence: {},
      },
    },
  };

  it("upgrades v1 records step by step without losing real actions", () => {
    const result = migrate<ProgressRecord>(
      structuredClone(v1),
      PROGRESS_VERSION,
      progressMigrations,
    );
    expect(result.status).toBe("migrated");
    if (result.status === "newer") throw new Error("unexpected");
    const data = result.data;
    expect(data.version).toBe(2);
    expect(data.lastLessonId).toBe("tool-selection");
    const lesson = data.lessons["tool-selection"];
    expect(lesson).not.toHaveProperty("quiz");
    expect(lesson.quizzes).toEqual({
      [LEGACY_QUIZ_ID]: { correct: 2, total: 3, at: later, attempts: 4, answers: {} },
    });
    expect(lesson.runs).toEqual({ count: 2, lastRunId: "r2", lastAt: later, seen: ["r2"] });
    expect(lesson.scenes).toEqual(v1.lessons["tool-selection"].scenes);
    expect(lesson.checkpoints).toEqual({ "quiz/1": at });
    expect(lesson.evidence).toEqual({ o1: { runId: "r1", at } });
    expect(data.lessons["dependent-calls"].quizzes).toEqual({});
    expect(data.lessons["dependent-calls"].runs.seen).toEqual([]);

    // 迁移后的记录继续正常工作：同一次运行不重复计数，新提交取代旧版整课记录。
    const next = [
      { type: "run_completed", lessonId: "tool-selection", runId: "r2", at },
      {
        type: "quiz_scored",
        lessonId: "tool-selection",
        quizId: "quiz",
        correct: 1,
        total: 1,
        answers: { q: { correct: true, confidence: "medium" } },
        at,
      },
    ] satisfies ProgressAction[];
    const after = next.reduce(reduceProgress, data).lessons["tool-selection"];
    expect(after.runs.count).toBe(2);
    expect(Object.keys(after.quizzes)).toEqual(["quiz"]);
    expect(after.quizzes.quiz.attempts).toBe(5);
  });

  it("migrates what the store loads from localStorage and writes back v2", () => {
    const storage = memoryStorage({ k: JSON.stringify(v1) });
    const store = createProgressStore(storage, "k");
    expect(store.writable).toBe(true);
    expect(store.get().lessons["tool-selection"].quizzes[LEGACY_QUIZ_ID].correct).toBe(2);
    store.dispatch({ type: "lesson_opened", lessonId: "tool-selection", at: later });
    expect(JSON.parse(storage.data.get("k")!).version).toBe(2);
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
