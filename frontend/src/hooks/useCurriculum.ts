import { useEffect, useState } from "react";
import { jsonFetch } from "../api";
import { createLanguageCache } from "../lib/languageCache";
import type { CurriculumData } from "../types";
import { useContentLanguage } from "./useContentLanguage";

// One request per language; every caller shares the same promise.
const catalogues = createLanguageCache((language) =>
  jsonFetch<CurriculumData>("/api/curriculum", undefined, language),
);

/**
 * Shared, cached curriculum catalogue in the UI language; null until loaded
 * or on failure. The previous language's catalogue stays until the new one
 * arrives.
 */
export function useCurriculum() {
  const language = useContentLanguage();
  const [data, setData] = useState<CurriculumData | null>(
    () => catalogues.peek(language) ?? null,
  );
  useEffect(() => {
    let alive = true;
    catalogues
      .load(language)
      .then((value) => alive && setData(value))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [language]);
  return data;
}

/** Category id of a lesson (e.g. "A"), once the catalogue is loaded. */
export function useLessonCategory(lessonId?: string) {
  const data = useCurriculum();
  return data?.lessons.find((lesson) => lesson.id === lessonId)?.category_id;
}
