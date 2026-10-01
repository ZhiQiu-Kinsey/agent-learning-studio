/**
 * Learning progress. Records only actions that really happened in this browser;
 * it never decides that something is "mastered". Stored in localStorage with
 * its own version line, independent of lesson content versions.
 */
import type { MigrationStep } from "../lib/migrate";

export const PROGRESS_VERSION = 1;

export const scenes = ["understand", "code", "lab", "check", "review"] as const;
export type Scene = (typeof scenes)[number];

export interface LessonProgress {
  firstOpenedAt: string;
  lastOpenedAt: string;
  /** Scene -> first visit time. */
  scenes: Partial<Record<Scene, string>>;
  runs: { count: number; lastRunId?: string; lastAt?: string };
  /** Latest self-check attempt; earlier attempts are counted, not kept. */
  quiz?: { correct: number; total: number; at: string; attempts: number };
  /** Learner-reported checkpoint id -> time ticked. */
  checkpoints: Record<string, string>;
  /** Observe point id -> the run where the learner found it. */
  evidence: Record<string, { runId: string; at: string }>;
}

export interface ProgressRecord {
  version: typeof PROGRESS_VERSION;
  lessons: Record<string, LessonProgress>;
  lastLessonId?: string;
}

export type ProgressAction =
  | { type: "lesson_opened"; lessonId: string; at: string }
  | { type: "scene_visited"; lessonId: string; scene: Scene; at: string }
  | { type: "run_completed"; lessonId: string; runId: string; at: string }
  | { type: "quiz_scored"; lessonId: string; correct: number; total: number; at: string }
  | { type: "checkpoint_set"; lessonId: string; checkpointId: string; done: boolean; at: string }
  | { type: "evidence_found"; lessonId: string; observeId: string; runId: string; at: string }
  | { type: "lessons_renamed"; mapping: Record<string, string> }
  | { type: "cleared" };

export const emptyProgress = (): ProgressRecord => ({
  version: PROGRESS_VERSION,
  lessons: {},
});

const blankLesson = (at: string): LessonProgress => ({
  firstOpenedAt: at,
  lastOpenedAt: at,
  scenes: {},
  runs: { count: 0 },
  checkpoints: {},
  evidence: {},
});

function withLesson(
  state: ProgressRecord,
  lessonId: string,
  at: string,
  update: (lesson: LessonProgress) => LessonProgress,
): ProgressRecord {
  const lesson = state.lessons[lessonId] ?? blankLesson(at);
  return { ...state, lessons: { ...state.lessons, [lessonId]: update(lesson) } };
}

export function reduceProgress(
  state: ProgressRecord,
  action: ProgressAction,
): ProgressRecord {
  switch (action.type) {
    case "lesson_opened":
      return {
        ...withLesson(state, action.lessonId, action.at, (lesson) => ({
          ...lesson,
          lastOpenedAt: action.at,
        })),
        lastLessonId: action.lessonId,
      };
    case "scene_visited":
      return withLesson(state, action.lessonId, action.at, (lesson) =>
        lesson.scenes[action.scene]
          ? lesson
          : { ...lesson, scenes: { ...lesson.scenes, [action.scene]: action.at } },
      );
    case "run_completed":
      return withLesson(state, action.lessonId, action.at, (lesson) =>
        lesson.runs.lastRunId === action.runId
          ? lesson // the same run reported twice (replay, reconnect) counts once
          : {
              ...lesson,
              runs: { count: lesson.runs.count + 1, lastRunId: action.runId, lastAt: action.at },
            },
      );
    case "quiz_scored": {
      if (action.total <= 0 || action.correct < 0 || action.correct > action.total)
        return state;
      return withLesson(state, action.lessonId, action.at, (lesson) => ({
        ...lesson,
        quiz: {
          correct: action.correct,
          total: action.total,
          at: action.at,
          attempts: (lesson.quiz?.attempts ?? 0) + 1,
        },
      }));
    }
    case "checkpoint_set":
      return withLesson(state, action.lessonId, action.at, (lesson) => {
        const checkpoints = { ...lesson.checkpoints };
        if (action.done) checkpoints[action.checkpointId] ??= action.at;
        else delete checkpoints[action.checkpointId];
        return { ...lesson, checkpoints };
      });
    case "evidence_found":
      return withLesson(state, action.lessonId, action.at, (lesson) =>
        lesson.evidence[action.observeId]
          ? lesson
          : {
              ...lesson,
              evidence: {
                ...lesson.evidence,
                [action.observeId]: { runId: action.runId, at: action.at },
              },
            },
      );
    case "lessons_renamed": {
      const lessons: Record<string, LessonProgress> = {};
      for (const [id, lesson] of Object.entries(state.lessons)) {
        const target = action.mapping[id] ?? id;
        // Never let an alias overwrite progress already stored under the new id.
        if (!lessons[target] || target === id) lessons[target] = lesson;
      }
      const last = state.lastLessonId;
      return {
        ...state,
        lessons,
        lastLessonId: last && (action.mapping[last] ?? last),
      };
    }
    case "cleared":
      return emptyProgress();
  }
}

/** Version 0 = nothing stored yet. */
export const progressMigrations: readonly MigrationStep[] = [
  { from: 0, to: 1, up: () => ({ lessons: {} }) },
];
