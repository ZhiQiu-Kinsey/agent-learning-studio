import { useSyncExternalStore } from "react";
import { createProgressStore, progressStorageKey } from "./store";
import type { QuizAnswer, Scene } from "./model";

export * from "./model";
export { createProgressStore, progressStorageKey } from "./store";
export { reviewNumbers } from "./summary";

function browserStorage() {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

export const progress = createProgressStore(browserStorage());

window.addEventListener("storage", (event) => {
  if (event.key === progressStorageKey || event.key === null) progress.reload();
});

export function useProgress() {
  return useSyncExternalStore(progress.subscribe, progress.get, progress.get);
}

const now = () => new Date().toISOString();

/** UI entry points; each records one action that really happened in this browser. */
export const track = {
  lessonOpened: (lessonId: string) =>
    progress.dispatch({ type: "lesson_opened", lessonId, at: now() }),
  sceneVisited: (lessonId: string, scene: Scene) =>
    progress.dispatch({ type: "scene_visited", lessonId, scene, at: now() }),
  runCompleted: (lessonId: string, runId: string) =>
    progress.dispatch({ type: "run_completed", lessonId, runId, at: now() }),
  quizScored: (
    lessonId: string,
    quizId: string,
    correct: number,
    total: number,
    answers?: Record<string, QuizAnswer>,
  ) =>
    progress.dispatch({
      type: "quiz_scored",
      lessonId,
      quizId,
      correct,
      total,
      answers,
      at: now(),
    }),
  /** 学习者在自己这次真实运行中找到了某条证据（观察点或轨迹找错）。 */
  evidenceFound: (
    lessonId: string,
    evidenceId: string,
    runId: string,
    seq?: number,
  ) =>
    progress.dispatch({
      type: "evidence_found",
      lessonId,
      observeId: evidenceId,
      runId,
      seq,
      at: now(),
    }),
  checkpointSet: (lessonId: string, checkpointId: string, done: boolean) =>
    progress.dispatch({
      type: "checkpoint_set",
      lessonId,
      checkpointId,
      done,
      at: now(),
    }),
};

/** Onboarding chapters share one progress entry; checkpoints are `<chapter>/<item>`. */
export const onboardingProgressId = "onboarding";
