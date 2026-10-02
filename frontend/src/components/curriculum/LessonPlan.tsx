import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, ExternalLink } from "lucide-react";
import { formatLessonNumber } from "../../lib/lessonIds";
import { httpUrl } from "../../lib/url";
import { useProgress } from "../../progress";
import type { CurriculumData, CurriculumLesson } from "../../types";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../ui/accordion";
import { Button } from "../ui/button";
import ElectricBorder from "../react-bits/ElectricBorder";
import { lessonMarks } from "./graph";
import { ProgressMarks } from "./ProgressMarks";
import { TextList } from "./TextList";

/** One lesson row of the list view; expands into the full lesson plan. */
export function LessonPlan({
  lesson,
  curriculum,
  onSelectLesson,
}: {
  lesson: CurriculumLesson;
  curriculum: CurriculumData;
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const marks = lessonMarks(useProgress(), lesson);
  // Electric outline only on lessons that can really be opened, while hovered/focused.
  const [hot, setHot] = useState(false);
  const live = lesson.status === "available";
  const prerequisiteTitles = lesson.prerequisites.map(
    (id) =>
      curriculum.lessons.find(
        (item) => item.id === id || item.aliases?.includes(id),
      )?.title || id,
  );
  return (
    <Accordion type="single" collapsible>
      <AccordionItem
        value={lesson.id}
        className="curriculum-lesson"
        data-status={lesson.status}
        data-testid="curriculum-lesson"
        onPointerEnter={live ? () => setHot(true) : undefined}
        onPointerLeave={live ? () => setHot(false) : undefined}
        onFocus={live ? () => setHot(true) : undefined}
        onBlur={
          live
            ? (event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node))
                  setHot(false);
              }
            : undefined
        }
      >
        {live && hot && (
          <ElectricBorder
            className="curriculum-lesson-electric"
            color="#8f7dff"
            chaos={0.06}
            speed={0.9}
            borderRadius={14}
          />
        )}
        <AccordionTrigger
          className="curriculum-lesson-trigger"
          data-testid="curriculum-lesson-trigger"
        >
          <span className="curriculum-lesson-title">
            <strong>{lesson.title}</strong>
            <small>
              {t("lessonMeta", {
                number: formatLessonNumber(lesson.number),
                level: lesson.level,
              })}
            </small>
          </span>
          <ProgressMarks marks={marks} testId="curriculum-lesson-progress" />
          <span className={`curriculum-status ${lesson.status}`}>
            {t(`status.${lesson.status}`)}
          </span>
        </AccordionTrigger>
        <AccordionContent className="curriculum-lesson-body">
          <p className="curriculum-summary">{lesson.summary}</p>
          <div className="curriculum-prerequisites">
            <strong>{t("list.prerequisites")}</strong>
            <p>
              {prerequisiteTitles.length
                ? prerequisiteTitles.join(t("list.separator"))
                : t("list.noPrerequisites")}
            </p>
          </div>
          <div className="curriculum-detail-grid">
            <section>
              <h4>{t("list.objectives")}</h4>
              <TextList items={lesson.objectives} />
            </section>
            <section>
              <h4>{t("list.topics")}</h4>
              <div className="curriculum-topics">
                {lesson.topics.map((topic) => (
                  <span key={topic}>{topic}</span>
                ))}
              </div>
            </section>
          </div>
          <section
            className="curriculum-experiments"
            data-testid="curriculum-lesson-experiments"
          >
            <h4>{t("list.experiments")}</h4>
            {lesson.experiments.map((experiment, index) => (
              <div className="curriculum-experiment" key={index}>
                <h5>{experiment.title}</h5>
                <ol>
                  {experiment.steps.map((step, stepIndex) => (
                    <li key={stepIndex}>{step}</li>
                  ))}
                </ol>
                <p>
                  <strong>{t("list.deliverable")}</strong>
                  {experiment.deliverable}
                </p>
              </div>
            ))}
          </section>
          <section>
            <h4>{t("list.acceptance")}</h4>
            <TextList items={lesson.acceptance} />
          </section>
          <section className="curriculum-references">
            <h4>{t("list.references")}</h4>
            <ul>
              {lesson.references.map((reference, index) => {
                const source = curriculum.sources.find(
                  (item) => item.id === reference.source,
                );
                const url = source ? httpUrl(source.url) : undefined;
                return (
                  <li key={index}>
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer">
                        {source?.title}
                        <ExternalLink size={11} />
                      </a>
                    ) : (
                      <span>{source?.title || reference.source}</span>
                    )}
                    <span> · {reference.locator}</span>
                  </li>
                );
              })}
            </ul>
          </section>
          {live ? (
            <Button
              className="primary-button"
              data-testid="curriculum-lesson-start"
              onClick={() => onSelectLesson(lesson.id)}
            >
              {t("list.start", { number: lesson.number })}
              <ArrowRight size={14} />
            </Button>
          ) : (
            <p className="curriculum-planned-note">{t("list.plannedNote")}</p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
