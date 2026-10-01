import { useCallback, useEffect, useRef, useState } from "react";
import { jsonFetch, readEventStream } from "../api";
import type { Detail, Lesson, Roadmap, Status, Trace } from "../types";

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
  const mounted = useRef(false);
  const runController = useRef<AbortController | null>(null);
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
        setLessonId(
          catalog.lessons.find((lesson) => lesson.available)?.id || "",
        );
      })
      .catch((reason) => {
        if (!abort.signal.aborted)
          setError(`无法连接教学服务：${messageOf(reason)}`);
      });
    void refreshStatus();
    return () => {
      mounted.current = false;
      abort.abort();
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
        setExerciseId(exercise?.id || "");
        setQuestion(exercise?.question || "");
        setInputs({ ...value.input_defaults, ...exercise?.inputs });
      })
      .catch((reason) => {
        if (!abort.signal.aborted) setLessonError(messageOf(reason));
      });
    return () => abort.abort();
  }, [lessonId]);

  useEffect(() => {
    if (!playing || running) return;
    const timer = window.setInterval(() => {
      setCursor((value) => {
        const next = Math.min(value + 1, events.length);
        setSelected(next - 1);
        if (next >= events.length) setPlaying(false);
        return next;
      });
    }, 950);
    return () => window.clearInterval(timer);
  }, [playing, running, events.length]);

  function selectLesson(id: string) {
    if (
      runController.current ||
      id === lessonId ||
      !lessons.some((lesson) => lesson.id === id && lesson.available)
    )
      return;
    setLessonId(id);
    setDetail(null);
    setExerciseId("");
    setQuestion("");
    setInputs({});
    setEvents([]);
    setCursor(0);
    setSelected(-1);
    setPlaying(false);
    setSource(0);
    setError("");
    setLessonError("");
  }

  function selectExercise(id: string) {
    if (runController.current) return;
    const exercise = detail?.exercises.find((item) => item.id === id);
    if (!exercise) return;
    setExerciseId(id);
    setQuestion(exercise.question);
    setInputs({ ...detail?.input_defaults, ...exercise.inputs });
  }

  function setInputs(value: Record<string, unknown>) {
    setRunInputs(value);
    setInputText(JSON.stringify(value, null, 2));
    setInputError("");
  }

  function editInputs(text: string) {
    if (runController.current) return;
    setInputText(text);
    try {
      const value: unknown = JSON.parse(text);
      if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error('请输入 JSON 对象，例如 {} 或 {"limit": 3}。');
      setRunInputs(value as Record<string, unknown>);
      setInputError("");
    } catch (reason) {
      setInputError(
        reason instanceof SyntaxError
          ? "JSON 格式不完整或有误，请检查引号、逗号和括号后再运行。"
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
    eventCount.current = 0;
    setRunning(true);
    setPlaying(false);
    setEvents([]);
    setCursor(0);
    setSelected(-1);
    setError("");
    const addEvent = (event: Trace) => {
      if (
        !mounted.current ||
        abort.signal.aborted ||
        runController.current !== abort
      )
        return;
      const index = eventCount.current++;
      setEvents((previous) => [...previous, event]);
      setCursor(index + 1);
      setSelected(index);
    };
    try {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lesson_id: lessonId,
          mode: "live",
          question,
          exercise_id: exerciseId,
          inputs: runInputs,
        }),
        signal: abort.signal,
      });
      await readEventStream(response, addEvent);
    } catch (reason) {
      if (!mounted.current) return;
      if (abort.signal.aborted) {
        setError(
          "已停止接收并请求取消后续步骤。已经发出的模型请求可能仍在完成，稍后可再次运行。",
        );
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
        if (mounted.current) setRunning(false);
      }
    }
  }

  function cancel() {
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
            { lesson_id: lessonId, mode: "live", events },
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
    setQuestion,
    inputs,
    inputText,
    inputError,
    setInputs,
    editInputs,
    selectExercise,
    run,
    canRun,
    requiresModel,
    cancel,
    running,
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
    download,
    source,
    setSource,
    refreshStatus,
  };
}

export type StudioState = ReturnType<typeof useStudio>;
