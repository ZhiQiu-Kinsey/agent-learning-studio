import { useEffect, useId, useState } from "react";
import { BookOpen, ChevronRight, LockKeyhole } from "lucide-react";
import { jsonFetch } from "../api";
import { formatLessonNumber } from "../lib/lessonIds";
import type { CurriculumData, Lesson } from "../types";
import { Button } from "./ui/button";

export function CourseNavigation({
  lessons,
  current,
  disabled,
  onSelect,
}: {
  lessons: Lesson[];
  current?: string;
  disabled: boolean;
  onSelect: (id: string) => void;
}) {
  const treeId = useId();
  const [data, setData] = useState<CurriculumData | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [expanded, setExpanded] = useState<string[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    jsonFetch<CurriculumData>("/api/curriculum", { signal: controller.signal })
      .then((value) => {
        setData(value);
        setExpanded([
          value.categories.find((category) =>
            category.modules.some((module) =>
              module.lesson_ids.includes(current || lessons[0]?.id),
            ),
          )?.id || value.categories[0]?.id,
        ]);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
    // Selection does not refetch or collapse the curriculum tree.
  }, [attempt]);
  useEffect(() => {
    if (!current || !data) return;
    const category = data.categories.find((item) =>
      item.modules.some((module) => module.lesson_ids.includes(current)),
    );
    if (category)
      setExpanded((previous) =>
        previous.includes(category.id) ? previous : [...previous, category.id],
      );
  }, [current, data]);
  const renderLesson = (
    lesson: { id: string; number?: number; title: string; status?: string },
    available: boolean,
  ) => (
    <Button
      type="button"
      key={lesson.id}
      variant="ghost"
      disabled={disabled || !available}
      className={`nav-lesson ${current === lesson.id ? "is-active" : ""}`}
      aria-current={current === lesson.id ? "page" : undefined}
      onClick={() => onSelect(lesson.id)}
      title={!available ? "计划中：本课尚未实现" : lesson.title}
    >
      <span className="nav-lesson-number">
        {formatLessonNumber(lesson.number)}
      </span>
      <span className="nav-lesson-title">
        {lesson.title.replace(/^第\s*\d+\s*课[：:]?\s*/, "")}
      </span>
      {!available && (
        <>
          <LockKeyhole size={11} aria-hidden="true" />
          <span className="nav-planned">计划中</span>
        </>
      )}
    </Button>
  );
  return (
    <nav className="course-tree" aria-label="课程列表">
      <div className="course-tree-heading">
        <span>课程导航</span>
        <small>
          {data
            ? `${data.lessons.filter((l) => l.status === "available" && lessons.some((item) => item.id === l.id)).length} / ${data.lessons.length} 已实现`
            : "正在加载"}
        </small>
      </div>
      {data ? (
        data.categories.map((category, index) => (
          <section className="nav-category" key={category.id}>
            <button
              className="nav-category-toggle"
              type="button"
              aria-expanded={expanded.includes(category.id)}
              aria-controls={`${treeId}-${category.id}`}
              onClick={() =>
                setExpanded((previous) =>
                  previous.includes(category.id)
                    ? previous.filter((id) => id !== category.id)
                    : [...previous, category.id],
                )
              }
            >
              <BookOpen size={14} />
              <span>{category.title}</span>
              <small>{String(index + 1).padStart(2, "0")}</small>
              <ChevronRight
                className={expanded.includes(category.id) ? "is-open" : ""}
                size={13}
              />
            </button>
            <div
              id={`${treeId}-${category.id}`}
              hidden={!expanded.includes(category.id)}
              className="nav-category-content"
            >
              {category.modules.map((module) => (
                <div className="nav-module" key={module.id}>
                  <h3>{module.title}</h3>
                  {module.lesson_ids.map((id) => {
                    const lesson = data.lessons.find((item) => item.id === id);
                    return lesson
                      ? renderLesson(
                          lesson,
                          lesson.status === "available" &&
                            lessons.some((item) => item.id === id),
                        )
                      : null;
                  })}
                </div>
              ))}
            </div>
          </section>
        ))
      ) : (
        <div className="nav-module">
          {lessons.map((lesson) => renderLesson(lesson, lesson.available))}
        </div>
      )}
      {error && (
        <div className="nav-load-error" role="alert">
          课程目录暂时不可用。
          <Button variant="link" onClick={() => setAttempt((a) => a + 1)}>
            重新加载
          </Button>
        </div>
      )}
    </nav>
  );
}
