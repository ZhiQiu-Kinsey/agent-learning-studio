import { useEffect, useId, useState, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { BookOpen, ChevronRight, LockKeyhole } from "lucide-react";
import { jsonFetch } from "../api";
import { formatLessonNumber } from "../lib/lessonIds";
import { useReducedMotion } from "../motion";
import type { CurriculumData, Lesson } from "../types";
import { tintFor } from "./backdrops/presets";
import { RailItem, useRailHighlight, useRailHovered } from "./shell/Rail";
import { CourseBranches } from "./shell/CourseBranches";
import { Button } from "./ui/button";

/** Each domain's glow follows the hue of its hero backdrop. */
export const domainTint = tintFor;

const fold = {
  type: "spring",
  stiffness: 380,
  damping: 36,
  mass: 0.8,
} as const;

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
  const { t } = useTranslation();
  const treeId = useId();
  const reduced = useReducedMotion();
  const hovered = useRailHovered();
  const hoveredLesson = hovered?.startsWith("lesson-")
    ? hovered.slice("lesson-".length)
    : null;
  const [data, setData] = useState<CurriculumData | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [expanded, setExpanded] = useState<string[]>([]);
  // Categories still animating closed; collapsed ones are `hidden` afterwards.
  const [closing, setClosing] = useState<string[]>([]);
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
  const toggle = (id: string) => {
    const closes = expanded.includes(id);
    setClosing((previous) =>
      closes && !reduced
        ? [...previous, id]
        : previous.filter((item) => item !== id),
    );
    setExpanded((previous) =>
      previous.includes(id)
        ? previous.filter((item) => item !== id)
        : [...previous, id],
    );
  };
  const renderLesson = (
    lesson: { id: string; number?: number; title: string; status?: string },
    available: boolean,
    index: number,
    tint?: string,
  ) => {
    const active = current === lesson.id;
    return (
      <RailItem
        type="button"
        key={lesson.id}
        itemKey={`lesson-${lesson.id}`}
        active={active}
        tint={tint}
        disabled={disabled || !available}
        className="nav-lesson"
        style={{ "--i": index } as CSSProperties}
        data-testid="course-nav-lesson"
        data-branch-id={lesson.id}
        data-branch-planned={!available || undefined}
        aria-current={active ? "page" : undefined}
        onClick={() => onSelect(lesson.id)}
        title={!available ? t("nav.plannedTitle") : lesson.title}
      >
        <span className="nav-lesson-number">
          {formatLessonNumber(lesson.number)}
        </span>
        <span className="nav-lesson-title">
          {lesson.title.replace(/^第\s*\d+\s*课[：:]?\s*/, "")}
        </span>
        {active && (
          <span
            className="nav-lesson-glow"
            aria-hidden="true"
            style={
              tint ? ({ "--rail-tint": tint } as CSSProperties) : undefined
            }
          />
        )}
        {!available && (
          <>
            <LockKeyhole size={11} aria-hidden="true" />
            <span className="nav-planned">{t("nav.planned")}</span>
          </>
        )}
      </RailItem>
    );
  };
  const implemented = data
    ? data.lessons.filter(
        (l) =>
          l.status === "available" && lessons.some((item) => item.id === l.id),
      ).length
    : 0;
  return (
    <nav
      className="course-tree"
      aria-label={t("nav.label")}
      data-testid="course-nav"
    >
      <div className="course-tree-heading">
        <span>{t("nav.heading")}</span>
        <small>
          {data
            ? t("nav.progress", {
                done: implemented,
                total: data.lessons.length,
              })
            : t("nav.loading")}
        </small>
      </div>
      {data ? (
        data.categories.map((category, index) => {
          const open = expanded.includes(category.id);
          const tint = domainTint(category.id);
          let order = 0;
          const signature = category.modules
            .flatMap((module) => module.lesson_ids)
            .map(
              (id) => `${id}:${lessons.some((item) => item.id === id) ? 1 : 0}`,
            )
            .join(",");
          return (
            <section
              className="nav-category"
              key={category.id}
              data-testid="course-nav-category"
              style={{ "--rail-tint": tint } as CSSProperties}
            >
              <CategoryToggle
                id={category.id}
                title={category.title}
                index={index}
                open={open}
                controls={`${treeId}-${category.id}`}
                onToggle={() => toggle(category.id)}
              />
              <motion.div
                id={`${treeId}-${category.id}`}
                hidden={!open && !closing.includes(category.id)}
                data-open={open || undefined}
                className="nav-category-content"
                initial={false}
                animate={
                  open
                    ? { height: "auto", opacity: 1 }
                    : { height: 0, opacity: 0 }
                }
                transition={reduced ? { duration: 0 } : fold}
                onAnimationComplete={() => {
                  if (!open)
                    setClosing((previous) =>
                      previous.filter((item) => item !== category.id),
                    );
                }}
              >
                <CourseBranches
                  open={open}
                  activeId={current}
                  hoveredId={hoveredLesson}
                  signature={signature}
                />
                {category.modules.map((module) => (
                  <div
                    className="nav-module"
                    key={module.id}
                    data-testid="course-nav-module"
                  >
                    <h3 data-branch-node="">{module.title}</h3>
                    {module.lesson_ids.map((id) => {
                      const lesson = data.lessons.find(
                        (item) => item.id === id,
                      );
                      return lesson
                        ? renderLesson(
                            lesson,
                            lesson.status === "available" &&
                              lessons.some((item) => item.id === id),
                            order++,
                            tint,
                          )
                        : null;
                    })}
                  </div>
                ))}
              </motion.div>
            </section>
          );
        })
      ) : (
        <div className="nav-module" data-testid="course-nav-module">
          {lessons.map((lesson, index) =>
            renderLesson(lesson, lesson.available, index),
          )}
        </div>
      )}
      {error && (
        <div className="nav-load-error" role="alert">
          {t("nav.loadError")}
          <Button variant="link" onClick={() => setAttempt((a) => a + 1)}>
            {t("nav.retry")}
          </Button>
        </div>
      )}
    </nav>
  );
}

function CategoryToggle({
  id,
  title,
  index,
  open,
  controls,
  onToggle,
}: {
  id: string;
  title: string;
  index: number;
  open: boolean;
  controls: string;
  onToggle: () => void;
}) {
  const { pills, handlers } = useRailHighlight(`category-${id}`);
  return (
    <button
      className="nav-category-toggle"
      data-testid="course-nav-category-toggle"
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      {...handlers}
    >
      {pills}
      <span className="nav-category-icon" aria-hidden="true">
        <BookOpen size={14} />
      </span>
      <span>{title}</span>
      <small>{String(index + 1).padStart(2, "0")}</small>
      <ChevronRight className={open ? "is-open" : ""} size={13} />
    </button>
  );
}
