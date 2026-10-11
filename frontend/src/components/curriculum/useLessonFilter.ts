import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { CurriculumData, CurriculumLesson } from "../../types";
import { lessonMatches } from "./graph";

/** Search, "only available" and domain filter shared by the roadmap and list views. */
export function useLessonFilter(curriculum: CurriculumData | null) {
  const [query, setQuery] = useState("");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const { t } = useTranslation("curriculum");

  const visibleIds = useMemo(() => {
    const filter = { query, onlyAvailable, categoryId: activeCategory };
    // Level and difficulty are fixed values shown through their codes: search the
    // label the learner sees (e.g. "Core" in English), not only the stored value.
    const labels = (lesson: CurriculumLesson) => [
      lesson.level_code ? t(`level.${lesson.level_code}`) : undefined,
      lesson.difficulty_code
        ? t(`difficulty.${lesson.difficulty_code}`)
        : lesson.difficulty,
    ];
    return new Set(
      curriculum?.lessons
        .filter((lesson) => lessonMatches(lesson, curriculum, filter, labels))
        .map((lesson) => lesson.id) ?? [],
    );
  }, [curriculum, query, onlyAvailable, activeCategory, t]);

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
