import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { ArrowRight } from "lucide-react";
import { useReducedMotion } from "../../../motion";
import type { CurriculumLesson } from "../../../types";
import { Button } from "../../ui/button";
import type { LessonMarks, RoadmapNode } from "../graph";
import { LessonFacts } from "../LessonPlan";
import { ProgressMarks } from "../ProgressMarks";

/** Detail of the lesson in focus, described by every node (aria-describedby). */
export function RoadmapDetail({
  lesson,
  node,
  marks,
  titleOf,
  onSelectLesson,
}: {
  lesson: CurriculumLesson;
  node: RoadmapNode;
  marks: LessonMarks;
  titleOf: (id: string) => string;
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  return (
    <motion.div
      className="roadmap-detail"
      id="roadmap-detail"
      data-testid="roadmap-detail"
      data-lesson-id={lesson.id}
      data-status={lesson.status}
      initial={reduced ? false : { opacity: 0, y: 10, filter: "blur(6px)" }}
      animate={{
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        transitionEnd: { filter: "none" },
      }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="roadmap-detail-head">
        <small>
          {t("lessonNumber", { number: lesson.number })} ·{" "}
          {t(`status.${lesson.status}`)}
          <LessonFacts lesson={lesson} />
        </small>
        <strong>{lesson.title}</strong>
        <ProgressMarks marks={marks} testId="roadmap-detail-progress" />
      </div>
      <p>{lesson.summary}</p>
      {!!lesson.sections?.length && (
        <ol
          className="roadmap-detail-sections"
          data-testid="roadmap-detail-sections"
          aria-label={t(
            lesson.status === "available"
              ? "list.sections"
              : "list.plannedSections",
          )}
        >
          {lesson.sections.map((section) => (
            <li key={section.title}>{section.title}</li>
          ))}
        </ol>
      )}
      <p className="roadmap-detail-prereqs">
        {node.prerequisites.length
          ? t("roadmap.prerequisites", {
              list: node.prerequisites.map(titleOf).join(t("list.separator")),
            })
          : t("roadmap.noPrerequisites")}
      </p>
      {lesson.status === "available" ? (
        <Button
          className="primary-button"
          data-testid="roadmap-detail-start"
          onClick={() => onSelectLesson(lesson.id)}
        >
          {t("roadmap.enter", { number: lesson.number })}
          <ArrowRight size={14} />
        </Button>
      ) : (
        <p
          className="curriculum-planned-note"
          data-testid="roadmap-detail-planned"
        >
          {t("roadmap.plannedNote")}
        </p>
      )}
    </motion.div>
  );
}
