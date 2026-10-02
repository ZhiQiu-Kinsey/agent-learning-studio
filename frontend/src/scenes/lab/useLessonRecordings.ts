import { useEffect, useState } from "react";
import { jsonFetch } from "../../api";
import type { RecordingMeta } from "./RecordingView";

/** Valid recordings shipped with a lesson; an unreachable list means none. */
export function useLessonRecordings(lessonId: string) {
  const [recordings, setRecordings] = useState<RecordingMeta[]>([]);
  useEffect(() => {
    const abort = new AbortController();
    jsonFetch<{ recordings: RecordingMeta[] }>(
      `/api/lessons/${encodeURIComponent(lessonId)}/recordings`,
      { signal: abort.signal },
    )
      .then((value) => {
        if (!abort.signal.aborted)
          setRecordings(
            value.recordings.filter((item) => item.valid && item.metadata),
          );
      })
      .catch(() => {
        if (!abort.signal.aborted) setRecordings([]);
      });
    return () => abort.abort();
  }, [lessonId]);
  return recordings;
}
