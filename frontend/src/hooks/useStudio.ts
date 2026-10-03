import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  cancelRun,
  createRun,
  followRunEvents,
  jsonFetch,
} from "../api";
import { resolveLessonId } from "../lib/lessonIds";
import { clientError } from "../i18n/errors";
import { track } from "../progress";
import {
  createReplayClock,
  type Gap,
  type ReplayOptions,
} from "../stage/replay";
import type { Detail, Lesson, Roadmap, Status, Trace } from "../types";
import { runCache, runKey } from "./runCache";

/** A finished run read back from the run store instead of calling the model again. */
export type RestoredRun = { runId: string; at: string; model: string };
type StoredRun = {
  exercise_id: string;
  status: string;
  model: string;
  created_at: string;
  finished_at: string | null;
};

const messageOf = (error: unknown) =>
  error instanceof Error ? error.message : String(error);

export function useStudio() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [roadmap, setRoadmap] = useState<Roadmap[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [lessonId, setLessonId] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [lessonError, setLessonError] = useState("");
  const [error, setError] = useState("");
  const [exerciseId, setExerciseId] = useState("");
  const [question, setQuestion] = useState("");
  const [inputs, setRunInputs] = useState<Record<string, unknown>>({});
  const [inputText, setInputText] = useState("{}");
  const [inputError, setInputError] = useState("");
  const [events, setEvents] = useState<Trace[]>([]);
  const [cursor, setCursor] = useState(0);
  const [selected, setSelected] = useState(-1);
  const [source, setSource] = useState(0);
  const [running, setRunning] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [replayOptions, setReplayOptions] = useState<ReplayOptions>({
    pacing: "uniform",
    speed: 1,
  });
  const [replayGap, setReplayGap] = useState<Gap | null>(null);
  const mounted = useRef(false);
  // A lesson picked before the catalog arrives is opened once it does.
  const pendingLesson = useRef("");
  const runController = useRef<AbortController | null>(null);
  // 当前运行的服务端 ID；断线续读、停止与页面关闭时的取消都作用于它。
  const activeRun = useRef<string | null>(null);
  const [runId, setRunId] = useState("");
  // 当前这份事件属于哪个练习：实验只拿自己对照组的运行核对证据。
  const [runExerciseId, setRunExerciseId] = useState("");
  // Set while the events on screen were read back from an earlier run (runCache).
  const [restored, setRestored] = useState<RestoredRun | null>(null);
  // Bumped by every run, lesson or exercise change: a slower restore then gives up.
  const restoreToken = useRef(0);
  const eventCount = useRef(0);
  const statusRequest = useRef(0);

  const refreshStatus = useCallback(async () => {
    const request = ++statusRequest.current;
    try {
      const value = await jsonFetch<Status>("/api/status");
      if (mounted.current && request === statusRequest.current)
        setStatus(value);
    } catch (reason) {
      if (mounted.current && request === statusRequest.current)
        setError(messageOf(reason));
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const abort = new AbortController();
    jsonFetch<{ lessons: Lesson[]; roadmap: Roadmap[] }>("/api/lessons", {
      signal: abort.signal,
    })
      .then((catalog) => {
        if (abort.signal.aborted) return;
        setLessons(catalog.lessons);
        setRoadmap(catalog.roadmap);
        const requested = resolveLessonId(
          pendingLesson.current,
          catalog.lessons,
        );
        pendingLesson.current = "";
        setLessonId(
          catalog.lessons.find(
            (lesson) => lesson.available && lesson.id === requested,
          )?.id ||
            catalog.lessons.find((lesson) => lesson.available)?.id ||
            "",
        );
      })
      .catch((reason) => {
        if (!abort.signal.aborted)
          setError(
            clientError("serviceUnreachable", { reason: messageOf(reason) }),
          );
      });
    void refreshStatus();
    // 运行在服务端后台执行；页面关闭时沿用旧语义，请求停止后续步骤。
    const stopActiveRun = () => {
      if (activeRun.current)
        void cancelRun(activeRun.current, true).catch(() => undefined);
    };
    window.addEventListener("pagehide", stopActiveRun);
    return () => {
      mounted.current = false;
      abort.abort();
      window.removeEventListener("pagehide", stopActiveRun);
      stopActiveRun();
      runController.current?.abort();
      ++statusRequest.current;
    };
  }, [refreshStatus]);

  useEffect(() => {
    if (!lessonId) return;
    const abort = new AbortController();
    setDetail(null);
    setLessonError("");
    jsonFetch<Detail>(`/api/lessons/${encodeURIComponent(lessonId)}`, {
      signal: abort.signal,
    })
      .then((value) => {
        if (abort.signal.aborted) return;
        setDetail(value);
        const exercise = value.exercises.find((item) => !item.offline_only);
        const defaults = { ...value.input_defaults, ...exercise?.inputs };
        setExerciseId(exercise?.id || "");
        setQuestion(exercise?.question || "");
        setInputs(defaults);
        if (exercise)
          void restore(value, exercise.id, exercise.question, defaults);
      })
      .catch((reason) => {
        if (!abort.signal.aborted) setLessonError(messageOf(reason));
      });
    return () => abort.abort();
  }, [lessonId]);

  // Replay only steps through recorded events. Any change of play state, events or
  // pacing disposes the clock, whose generation token drops stale timers.
  const cursorRef = useRef(cursor);
  cursorRef.current = cursor;
  useEffect(() => {
    if (!playing || running) return;
    const clock = createReplayClock(
      events.map((event) => event.timestamp),
      (state) => {
        setCursor(state.cursor);
        setSelected(state.cursor - 1);
        setReplayGap(state.waiting);
        if (!state.playing) setPlaying(false);
      },
      undefined,
      { cursor: cursorRef.current, options: replayOptions },
    );
    clock.play();
    return () => {
      clock.dispose();
      setReplayGap(null);
    };
  }, [playing, running, events, replayOptions]);

  function selectLesson(requested: string) {
    if (!lessons.length) {
      pendingLesson.current = requested;
      return;
    }
    // Legacy numeric ids still work; state always holds the canonical slug.
    const id = resolveLessonId(requested, lessons);
    if (
      runController.current ||
      !id ||
      id === lessonId ||
      !lessons.some((lesson) => lesson.id === id && lesson.available)
    )
      return;
    restoreToken.current++;
    setRestored(null);
    setLessonId(id);
    setDetail(null);
    setExerciseId("");
    setQuestion("");
    setInputs({});
    setEvents([]);
    setRunExerciseId("");
    setCursor(0);
    setSelected(-1);
    setPlaying(false);
    setSource(0);
    setError("");
    setLessonError("");
  }

  function selectExercise(id: string) {
    if (runController.current || !detail) return;
    const exercise = detail.exercises.find((item) => item.id === id);
    if (!exercise) return;
    const defaults = { ...detail.input_defaults, ...exercise.inputs };
    setExerciseId(id);
    setQuestion(exercise.question);
    setInputs(defaults);
    void restore(detail, id, exercise.question, defaults);
  }

  /**
   * Shows the learner's last finished run of this exercise when nothing that
   * shapes it has changed (runKey), read back from the run store; the model is
   * not called. Without such a run the screen keeps whatever it showed.
   */
  async function restore(
    lesson: Detail,
    exercise: string,
    text: string,
    values: Record<string, unknown>,
  ) {
    const token = ++restoreToken.current;
    const key = runKey(lesson, exercise, text, values);
    const id = runCache.get(key);
    if (!id) return;
    const stale = () =>
      token !== restoreToken.current ||
      !!runController.current ||
      !mounted.current;
    try {
      const run = await jsonFetch<StoredRun>(
        `/api/runs/${encodeURIComponent(id)}`,
      );
      if (run.status !== "completed" || run.exercise_id !== exercise) {
        runCache.forget(key);
        return;
      }
      const stored: Trace[] = [];
      await followRunEvents(id, (event) => stored.push(event));
      if (stale() || stored.at(-1)?.type !== "done") return;
      setPlaying(false);
      setEvents(stored);
      setCursor(stored.length);
      setSelected(stored.length - 1);
      setRunId(id);
      setRunExerciseId(exercise);
      setError("");
      setRestored({
        runId: id,
        at: run.finished_at ?? run.created_at,
        model: run.model,
      });
    } catch (reason) {
      // The learner cleared the run records: forget the id. Other failures
      // just leave the screen as it was; running again always works.
      if (reason instanceof ApiError && reason.status === 404)
        runCache.forget(key);
    }
  }

  function changeQuestion(value: string) {
    setQuestion(value);
    // The run on screen no longer answers this question.
    setRestored(null);
  }

  function setInputs(value: Record<string, unknown>) {
    setRunInputs(value);
    setInputText(JSON.stringify(value, null, 2));
    setInputError("");
  }

  function editInputs(text: string) {
    if (runController.current) return;
    setRestored(null);
    setInputText(text);
    try {
      const value: unknown = JSON.parse(text);
      if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error(clientError("inputsNotObject"));
      setRunInputs(value as Record<string, unknown>);
      setInputError("");
    } catch (reason) {
      setInputError(
        reason instanceof SyntaxError
          ? clientError("inputsSyntax")
          : messageOf(reason),
      );
    }
  }

  async function run(
    runInputs: Record<string, unknown> = inputs,
  ): Promise<void> {
    if (!detail || runController.current || inputError) return;
    // Custom runtimes may accept only structured inputs; standard lessons keep
    // the same question/exercise contract. The server validates the payload.
    if (!question.trim() && !detail.capabilities?.supports_inputs) return;
    const abort = new AbortController();
    runController.current = abort;
    restoreToken.current++;
    setRestored(null);
    const key = runKey(detail, exerciseId, question, runInputs);
    let last: Trace | null = null;
    eventCount.current = 0;
    setRunning(true);
    setPlaying(false);
    setEvents([]);
    setRunExerciseId(exerciseId);
    setCursor(0);
    setSelected(-1);
    setError("");
    setRunId("");
    const addEvent = (event: Trace) => {
      if (
        !mounted.current ||
        abort.signal.aborted ||
        runController.current !== abort
      )
        return;
      const index = eventCount.current++;
      last = event;
      setEvents((previous) => [...previous, event]);
      setCursor(index + 1);
      setSelected(index);
    };
    try {
      // 创建请求不随停止中断：必须拿到 run_id，才能让服务端停止已开始的运行。
      const id = await createRun({
        lesson_id: lessonId,
        mode: "live",
        question,
        exercise_id: exerciseId,
        inputs: runInputs,
      });
      if (abort.signal.aborted) {
        void cancelRun(id).catch(() => undefined);
        throw new DOMException(clientError("stopped"), "AbortError");
      }
      if (runController.current === abort) {
        activeRun.current = id;
        if (mounted.current) setRunId(id);
      }
      // 断线时按最后收到的 seq 自动续读；服务端存储保证不重不漏。
      await followRunEvents(id, addEvent, { signal: abort.signal });
      // Reached the server's done event: one real run, counted once per run_id.
      track.runCompleted(lessonId, id);
      // A completed run answers this question until something that shapes it changes.
      const final = last as Trace | null;
      if (final?.type === "done" && final.data.status === "completed")
        runCache.remember(key, id);
    } catch (reason) {
      if (!mounted.current) return;
      if (abort.signal.aborted) {
        setError(clientError("stoppedNotice"));
      } else {
        const message = messageOf(reason);
        setError(message);
        addEvent({
          type: "error",
          round: null,
          timestamp: new Date().toISOString(),
          data: { message },
        });
      }
    } finally {
      if (runController.current === abort) {
        runController.current = null;
        activeRun.current = null;
        if (mounted.current) setRunning(false);
      }
    }
  }

  function cancel() {
    const id = activeRun.current;
    if (id) void cancelRun(id).catch(() => undefined);
    runController.current?.abort();
  }
  function selectEvent(index: number) {
    if (Number.isInteger(index) && index >= 0 && index < cursor)
      setSelected(index);
  }
  function seek(value: number) {
    if (runController.current || !Number.isFinite(value)) return;
    const next = Math.max(0, Math.min(Math.round(value), events.length));
    setPlaying(false);
    setCursor(next);
    setSelected(next - 1);
  }
  function replay() {
    if (runController.current || !events.length) return;
    if (cursor >= events.length) {
      setCursor(0);
      setSelected(-1);
    }
    setPlaying((value) => !value);
  }
  function step() {
    seek(cursor + 1);
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            {
              lesson_id: lessonId,
              mode: "live",
              run_id: runId || null,
              events,
            },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `agent-lab-${lessonId}-${Date.now()}.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const visible = events.slice(0, cursor);
  const active = selected >= 0 && selected < cursor ? events[selected] : null;
  const answer = visible.findLast((event) => event.type === "answer");
  const requiresModel = detail?.capabilities?.requires_model !== false;
  const canRun =
    !inputError &&
    (!requiresModel ||
      (!!status?.config_ready &&
        (status.requires_api_key === false || status.api_key_configured)));
  return {
    lessons,
    roadmap,
    status,
    lessonId,
    detail,
    lessonError,
    error,
    setError,
    selectLesson,
    exerciseId,
    question,
    setQuestion: changeQuestion,
    inputs,
    inputText,
    inputError,
    setInputs: (value: Record<string, unknown>) => {
      setInputs(value);
      setRestored(null);
    },
    editInputs,
    selectExercise,
    run,
    canRun,
    requiresModel,
    cancel,
    running,
    runId,
    runExerciseId,
    restored,
    events,
    visible,
    active,
    answer,
    cursor,
    selectEvent,
    seek,
    replay,
    step,
    playing,
    replayOptions,
    setReplayOptions,
    replayGap,
    download,
    source,
    setSource,
    refreshStatus,
  };
}

export type StudioState = ReturnType<typeof useStudio>;
