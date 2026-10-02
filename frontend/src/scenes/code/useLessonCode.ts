import { useEffect, useState } from "react";
import { jsonFetch } from "../../api";
import type { LessonCode } from "./model";

type State =
  | { status: "loading"; code: null; error: "" }
  | { status: "ready"; code: LessonCode; error: "" }
  | { status: "error"; code: null; error: string };

/** Symbols, “what's new” and annotations computed by the server from the lesson's real sources. */
export function useLessonCode(lessonId: string | undefined): State {
  const [state, setState] = useState<State>({
    status: "loading",
    code: null,
    error: "",
  });
  useEffect(() => {
    if (!lessonId) return;
    const abort = new AbortController();
    setState({ status: "loading", code: null, error: "" });
    jsonFetch<LessonCode>(`/api/lessons/${encodeURIComponent(lessonId)}/code`, {
      signal: abort.signal,
    })
      .then((code) => {
        if (!abort.signal.aborted)
          setState({ status: "ready", code, error: "" });
      })
      .catch((reason: unknown) => {
        if (!abort.signal.aborted)
          setState({
            status: "error",
            code: null,
            error: reason instanceof Error ? reason.message : String(reason),
          });
      });
    return () => abort.abort();
  }, [lessonId]);
  return state;
}
