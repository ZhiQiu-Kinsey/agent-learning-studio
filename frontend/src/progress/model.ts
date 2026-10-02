/**
 * Learning progress. Records only actions that really happened in this browser;
 * it never decides that something is "mastered". Stored in localStorage with
 * its own version line, independent of lesson content versions.
 */
import type { MigrationStep } from "../lib/migrate";

export const PROGRESS_VERSION = 2;

export const scenes = ["understand", "code", "lab", "check", "review"] as const;
export type Scene = (typeof scenes)[number];

/** 作答前学习者自评的把握程度（3 档）；只是自报，不参与计分。 */
export const confidenceLevels = ["low", "medium", "high"] as const;
export type Confidence = (typeof confidenceLevels)[number];

export interface QuizAnswer {
  correct: boolean;
  confidence?: Confidence;
}

/** 一个自测块最近一次提交；更早的提交只计次数，不保留明细。 */
export interface QuizAttempt {
  correct: number;
  total: number;
  at: string;
  attempts: number;
  /** Question id -> 这次是否答对、作答前的信心。v1 迁移来的记录没有明细。 */
  answers: Record<string, QuizAnswer>;
}

/** v1 只按课记录一次自测；迁移后放在这个键下，不会与内容 id（小写短横线）冲突。 */
export const LEGACY_QUIZ_ID = "*v1";

/** 最多记住这么多个已计数的 run_id，用来保证同一次运行只计一次。 */
export const RUN_ID_MEMORY = 200;

export interface LessonProgress {
  firstOpenedAt: string;
  lastOpenedAt: string;
  /** Scene -> first visit time. */
  scenes: Partial<Record<Scene, string>>;
  runs: {
    count: number;
    lastRunId?: string;
    lastAt?: string;
    /** 已计数的 run_id（最近 RUN_ID_MEMORY 个）。 */
    seen: string[];
  };
  /** Quiz block id -> latest attempt. */
  quizzes: Record<string, QuizAttempt>;
  /** Learner-reported checkpoint id -> time ticked. */
  checkpoints: Record<string, string>;
  /**
   * Evidence id -> the run where the learner found it. Keys are observe point
   * ids, or `trace-hunt:<block id>` for trace hunts in 自检.
   */
  evidence: Record<string, { runId: string; at: string; seq?: number }>;
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
  | {
      type: "quiz_scored";
      lessonId: string;
      quizId: string;
      correct: number;
      total: number;
      answers?: Record<string, QuizAnswer>;
      at: string;
    }
  | { type: "checkpoint_set"; lessonId: string; checkpointId: string; done: boolean; at: string }
  | {
      type: "evidence_found";
      lessonId: string;
      observeId: string;
      runId: string;
      seq?: number;
      at: string;
    }
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
  runs: { count: 0, seen: [] },
  quizzes: {},
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

const isConfidence = (value: unknown): value is Confidence =>
  (confidenceLevels as readonly unknown[]).includes(value);

/** 分数必须自洽：明细题数与总题数一致、答对数与明细一致，信心只能取已知档位。 */
function validScore(action: Extract<ProgressAction, { type: "quiz_scored" }>) {
  const { correct, total, answers } = action;
  if (!Number.isInteger(correct) || !Number.isInteger(total)) return false;
  if (total <= 0 || correct < 0 || correct > total) return false;
  if (!answers) return true;
  const values = Object.values(answers);
  return (
    values.length === total &&
    values.filter((answer) => answer.correct).length === correct &&
    values.every(
      (answer) => answer.confidence === undefined || isConfidence(answer.confidence),
    )
  );
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
        lesson.runs.lastRunId === action.runId || lesson.runs.seen.includes(action.runId)
          ? lesson // the same run reported again (replay, reconnect) counts once
          : {
              ...lesson,
              runs: {
                count: lesson.runs.count + 1,
                lastRunId: action.runId,
                lastAt: action.at,
                seen: [...lesson.runs.seen, action.runId].slice(-RUN_ID_MEMORY),
              },
            },
      );
    case "quiz_scored": {
      if (!validScore(action)) return state;
      return withLesson(state, action.lessonId, action.at, (lesson) => {
        // 新提交取代 v1 遗留的整课记录，并延续它的提交次数。
        const { [LEGACY_QUIZ_ID]: legacy, ...quizzes } = lesson.quizzes;
        const previous = quizzes[action.quizId] ?? legacy;
        return {
          ...lesson,
          quizzes: {
            ...quizzes,
            [action.quizId]: {
              correct: action.correct,
              total: action.total,
              at: action.at,
              attempts: (previous?.attempts ?? 0) + 1,
              answers: action.answers ?? {},
            },
          },
        };
      });
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
                [action.observeId]: {
                  runId: action.runId,
                  at: action.at,
                  ...(action.seq === undefined ? {} : { seq: action.seq }),
                },
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

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json =>
  !!value && typeof value === "object" && !Array.isArray(value);

/**
 * v1 -> v2：整课的 quiz 移到 quizzes[LEGACY_QUIZ_ID]（没有逐题明细）；
 * runs 增加 seen，用 lastRunId 起步，保证迁移后同一次运行仍只计一次。
 */
export function progressV1toV2(data: Json): Json {
  const lessons: Record<string, unknown> = {};
  for (const [id, value] of Object.entries(isObject(data.lessons) ? data.lessons : {})) {
    if (!isObject(value)) continue;
    const { quiz, ...lesson } = value;
    const runs = isObject(lesson.runs) ? lesson.runs : { count: 0 };
    lessons[id] = {
      ...lesson,
      runs: {
        ...runs,
        seen: typeof runs.lastRunId === "string" ? [runs.lastRunId] : [],
      },
      quizzes: isObject(quiz) ? { [LEGACY_QUIZ_ID]: { ...quiz, answers: {} } } : {},
    };
  }
  return { ...data, lessons };
}

/** Version 0 = nothing stored yet. */
export const progressMigrations: readonly MigrationStep[] = [
  { from: 0, to: 1, up: () => ({ lessons: {} }) },
  { from: 1, to: 2, up: progressV1toV2 },
];

/** 自检里轨迹找错的证据键，与实验观察点的键分开。 */
export const huntEvidenceId = (blockId: string) => `trace-hunt:${blockId}`;
