import { useMemo, useState } from "react";
import type { CurriculumData } from "../../types";
import { lessonMatches } from "./graph";

/** Search, "only available" and domain filter shared by the roadmap and list views. */
export function useLessonFilter(curriculum: CurriculumData | null) {
  const [query, setQuery] = useState("");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const visibleIds = useMemo(() => {
    const filter = { query, onlyAvailable, categoryId: activeCategory };
    return new Set(
      curriculum?.lessons
        .filter((lesson) => lessonMatches(lesson, curriculum, filter))
        .map((lesson) => lesson.id) ?? [],
    );
  }, [curriculum, query, onlyAvailable, activeCategory]);

  const reset = () => {
    setActiveCategory(null);
    setQuery("");
    setOnlyAvailable(false);
  };

  return {
    query,
    setQuery,
    onlyAvailable,
    setOnlyAvailable,
    activeCategory,
    setActiveCategory,
    visibleIds,
    reset,
  };
}

export type LessonFilterState = ReturnType<typeof useLessonFilter>;
