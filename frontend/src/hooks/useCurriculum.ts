import { useEffect, useState } from "react";
import { jsonFetch } from "../api";
import type { CurriculumData } from "../types";

// One request per page load; every caller shares the same promise.
let pending: Promise<CurriculumData> | null = null;
const load = () =>
  (pending ??= jsonFetch<CurriculumData>("/api/curriculum").catch((error) => {
    pending = null;
    throw error;
  }));

/** Shared, cached curriculum catalogue; null until loaded or on failure. */
export function useCurriculum() {
  const [data, setData] = useState<CurriculumData | null>(null);
  useEffect(() => {
    let alive = true;
    load()
      .then((value) => alive && setData(value))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  return data;
}

/** Category id of a lesson (e.g. "A"), once the catalogue is loaded. */
export function useLessonCategory(lessonId?: string) {
  const data = useCurriculum();
  return data?.lessons.find((lesson) => lesson.id === lessonId)?.category_id;
}
