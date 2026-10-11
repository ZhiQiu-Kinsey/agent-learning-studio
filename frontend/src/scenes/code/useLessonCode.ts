import { useEffect, useRef, useState } from "react";
import { jsonFetch } from "../../api";
import { useContentLanguage } from "../../hooks/useContentLanguage";
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
  const language = useContentLanguage();
  // A language switch swaps the notes in place; only a new lesson shows "loading".
  const loaded = useRef("");
  useEffect(() => {
    if (!lessonId) return;
    const abort = new AbortController();
    if (loaded.current !== lessonId)
      setState({ status: "loading", code: null, error: "" });
    jsonFetch<LessonCode>(
      `/api/lessons/${encodeURIComponent(lessonId)}/code`,
      { signal: abort.signal },
      language,
    )
      .then((code) => {
        if (abort.signal.aborted) return;
        loaded.current = lessonId;
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
  }, [lessonId, language]);
  return state;
}
