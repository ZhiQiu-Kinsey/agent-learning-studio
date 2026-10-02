import { lazy, Suspense, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, LoaderCircle, LockKeyhole } from "lucide-react";
import { formatLessonNumber } from "../../lib/lessonIds";
import type { ProgressRecord } from "../../progress";
import type { CurriculumLesson } from "../../types";
import { lessonMarks, stagesOf, type CurriculumGraph } from "./graph";
import { ProgressMarks } from "./ProgressMarks";

const RoadmapView = lazy(() => import("./RoadmapView"));

const narrowQuery = "(max-width: 720px)";
const subscribeNarrow = (onChange: () => void) => {
  const media = matchMedia(narrowQuery);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
};
const isNarrow = () => matchMedia(narrowQuery).matches;

interface SectionProps {
  graph: CurriculumGraph;
  lessons: CurriculumLesson[];
  progress: ProgressRecord;
  matches: ReadonlySet<string>;
  onSelectLesson: (id: string) => void;
}

/** Narrow screens: the same route as stages in a vertical list, no canvas. */
function RoadmapList({
  graph,
  lessons,
  progress,
  matches,
  onSelectLesson,
}: SectionProps) {
  const { t } = useTranslation("curriculum");
  const lessonById = new Map(lessons.map((lesson) => [lesson.id, lesson]));
  const numberOf = (id: string) =>
    formatLessonNumber(lessonById.get(id)?.number);
  return (
    <ol
      className="roadmap-list"
      data-testid="curriculum-roadmap-list"
      aria-label={t("roadmap.label")}
    >
      {stagesOf(graph).map((stage, index) => (
        <li key={index} className="roadmap-stage">
          <h3>{t("roadmap.stage", { index: index + 1 })}</h3>
          <ul>
            {stage.map((node) => {
              const lesson = lessonById.get(node.id);
              const marks = lessonMarks(progress, lesson ?? node);
              const body = (
                <>
                  <span className="roadmap-node-number">
                    {formatLessonNumber(node.number)}
                  </span>
                  <span className="roadmap-list-text">
                    <strong>{node.title}</strong>
                    <small>
                      {node.prerequisites.length
                        ? t("roadmap.prerequisites", {
                            list: node.prerequisites
                              .map(numberOf)
                              .join(t("list.separator")),
                          })
                        : t("roadmap.noPrerequisites")}
                    </small>
                  </span>
                  <span className="roadmap-node-meta">
                    {node.status === "planned" && (
                      <LockKeyhole size={11} aria-hidden="true" />
                    )}
                    {t(`status.${node.status}`)}
                  </span>
                  <ProgressMarks marks={marks} testId="roadmap-node-progress" />
                </>
              );
              return (
                <li
                  key={node.id}
                  className="roadmap-list-item"
                  data-testid="roadmap-list-item"
                  data-lesson-id={node.id}
                  data-status={node.status}
                  data-dimmed={!matches.has(node.id)}
                >
                  {node.status === "available" ? (
                    <button
                      type="button"
                      onClick={() => onSelectLesson(node.id)}
                      aria-label={t("roadmap.enter", { number: node.number })}
                    >
                      {body}
                      <ArrowRight size={14} aria-hidden="true" />
                    </button>
                  ) : (
                    <div>{body}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ol>
  );
}

export function RoadmapSection(props: SectionProps) {
  const { t } = useTranslation("curriculum");
  const narrow = useSyncExternalStore(subscribeNarrow, isNarrow, () => false);
  return (
    <section className="curriculum-roadmap" aria-labelledby="roadmap-title">
      <div className="curriculum-section-heading">
        <h2 id="roadmap-title">{t("roadmap.label")}</h2>
        <span>{narrow ? t("roadmap.listHelp") : t("roadmap.help")}</span>
      </div>
      <div className="roadmap-legend" aria-hidden="true">
        <span data-status="available">{t("roadmap.legendAvailable")}</span>
        <span data-status="planned">{t("roadmap.legendPlanned")}</span>
      </div>
      {narrow ? (
        <RoadmapList {...props} />
      ) : (
        <Suspense
          fallback={
            <p className="roadmap-loading" role="status">
              <LoaderCircle size={18} className="spin" aria-hidden="true" />
              {t("roadmap.loading")}
            </p>
          }
        >
          <RoadmapView {...props} />
        </Suspense>
      )}
    </section>
  );
}
