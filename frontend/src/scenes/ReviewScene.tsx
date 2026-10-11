import { useEffect, useState } from "react";
import { ArrowRight, Check, Circle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { jsonFetch } from "../api";
import { useContentLanguage } from "../hooks/useContentLanguage";
import CountUp from "../components/react-bits/CountUp";
import { Button } from "../components/ui/button";
import { LearningBadge } from "../components/learning/LearningBadge";
import { formatLessonNumber } from "../lib/lessonIds";
import { useReducedMotion } from "../motion";
import { confidenceLevels, reviewNumbers, useProgress } from "../progress";
import type { CurriculumData, CurriculumLesson } from "../types";
import { sceneIds, type SceneProps } from "./types";
import "../styles/self-check.css";

function Stat({
  id,
  value,
  label,
  hint,
}: {
  id: string;
  value: number;
  label: string;
  hint: string;
}) {
  const reduced = useReducedMotion();
  return (
    <div
      className="review-stat"
      data-testid={`review-${id}`}
      data-value={value}
    >
      <dt>{label}</dt>
      <dd>
        {/* 数值只在入场时滚动一次；减少动画时直接显示最终值。 */}
        {reduced || value === 0 ? (
          <span className="review-number">{value}</span>
        ) : (
          <CountUp className="review-number" to={value} duration={0.8} />
        )}
        <small>{hint}</small>
      </dd>
    </div>
  );
}

/** 回顾：只用本机真实记录，不推断“已掌握”。 */
export function ReviewScene({ studio }: SceneProps) {
  const { t } = useTranslation("lesson", { keyPrefix: "review" });
  const { t: tl } = useTranslation("lesson");
  const { t: tq } = useTranslation("quiz");
  const detail = studio.detail!;
  const progress = useProgress();
  const record = progress.lessons[detail.id];
  const numbers = reviewNumbers(record);
  const hasActivity = numbers.hasActivity;
  const capabilities = detail.learning?.capabilities ?? [];
  const confidenceRows = confidenceLevels.filter(
    (level) => numbers.confidence[level].answered > 0,
  );

  const [curriculum, setCurriculum] = useState<CurriculumData | "error" | null>(
    null,
  );
  const language = useContentLanguage();
  useEffect(() => {
    const controller = new AbortController();
    jsonFetch<CurriculumData>(
      "/api/curriculum",
      { signal: controller.signal },
      language,
    )
      .then(setCurriculum)
      .catch(() => {
        if (!controller.signal.aborted) setCurriculum("error");
      });
    return () => controller.abort();
  }, [language]);
  const lessons =
    curriculum && curriculum !== "error"
      ? [...curriculum.lessons].sort((a, b) => a.number - b.number)
      : [];
  const position = lessons.findIndex((lesson) => lesson.id === detail.id);
  const next: CurriculumLesson | undefined =
    position >= 0 ? lessons[position + 1] : undefined;
  const titleOf = (id: string) =>
    lessons.find((lesson) => lesson.id === id)?.title ?? id;

  return (
    <section
      className="scene-review"
      data-testid="scene-review"
      aria-label={t("title")}
    >
      <header className="review-header">
        <h2>{t("title")}</h2>
        <p>{t("help")}</p>
      </header>

      {hasActivity ? (
        <dl className="review-stats" aria-label={t("stats.region")}>
          <Stat
            id="runs"
            value={numbers.runs}
            label={t("stats.runs")}
            hint={t("stats.runsHint")}
          />
          <Stat
            id="quiz"
            value={numbers.quizCorrect}
            label={t("stats.quiz")}
            hint={
              numbers.quizTotal
                ? t("stats.quizHint", { total: numbers.quizTotal })
                : t("stats.quizNone")
            }
          />
          <Stat
            id="checkpoints"
            value={numbers.checkpoints}
            label={t("stats.checkpoints")}
            hint={t("stats.checkpointsHint")}
          />
          <Stat
            id="evidence"
            value={numbers.evidence}
            label={t("stats.evidence")}
            hint={t("stats.evidenceHint")}
          />
        </dl>
      ) : (
        <p className="review-empty" data-testid="review-empty">
          {t("empty")}
        </p>
      )}

      {/* After the counters, so the real numbers are the first thing in view. */}
      <LearningBadge
        number={formatLessonNumber(detail.number)}
        title={
          lessons.find((lesson) => lesson.id === detail.id)?.title ??
          detail.title
        }
        record={record}
        quizAttempts={numbers.quizAttempts}
      >
        <div className="review-grid">
          <section className="review-card" data-testid="review-scenes">
            <h3>{t("scenes.title")}</h3>
            <ul className="review-scenes">
              {sceneIds.map((scene) => {
                const visited = !!record?.scenes[scene];
                return (
                  <li
                    key={scene}
                    data-scene={scene}
                    data-visited={visited}
                    className={visited ? "is-visited" : undefined}
                  >
                    {visited ? (
                      <Check size={14} aria-hidden="true" />
                    ) : (
                      <Circle size={14} aria-hidden="true" />
                    )}
                    {tl(`scenes.${scene}`)}
                    <span className="sr-only">
                      {visited ? t("scenes.visited") : t("scenes.notVisited")}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>

          {numbers.quizAttempts > 0 && (
            <section className="review-card" data-testid="review-confidence">
              <h3>{t("confidence.title")}</h3>
              {confidenceRows.length ? (
                <ul className="review-confidence">
                  {confidenceRows.map((level) => (
                    <li key={level} data-level={level}>
                      <b>{tq(`confidence.${level}`)}</b>
                      {t("confidence.row", numbers.confidence[level])}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>{t("confidence.none")}</p>
              )}
              <p className="review-muted">
                {t("quiz.attempts", { count: numbers.quizAttempts })}
                {numbers.hasLegacyQuiz && ` ${t("quiz.legacy")}`}
              </p>
            </section>
          )}

          <section className="review-card" data-testid="review-capabilities">
            <h3>{t("capabilities.title")}</h3>
            {capabilities.length ? (
              <ul className="lesson-capabilities">
                {capabilities.map((capability) => (
                  <li key={capability} data-capability={capability}>
                    {tl(`capabilities.${capability}`)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="review-muted">{t("capabilities.none")}</p>
            )}
          </section>

          <section className="review-card" data-testid="review-next">
            <h3>{t("next.title")}</h3>
            {curriculum === null && (
              <p className="review-muted" role="status">
                {t("next.loading")}
              </p>
            )}
            {curriculum === "error" && (
              <p className="review-muted">{t("next.unavailable")}</p>
            )}
            {curriculum && curriculum !== "error" && !next && (
              <p className="review-muted">{t("next.last")}</p>
            )}
            {next && (
              <>
                <p className="review-next-title" data-lesson={next.id}>
                  <span className="review-next-number">
                    {formatLessonNumber(next.number)}
                  </span>
                  {next.title}
                </p>
                <h4>{t("next.prerequisites")}</h4>
                {next.prerequisites.length ? (
                  <ul className="review-prerequisites">
                    {next.prerequisites.map((id) => {
                      const runs = progress.lessons[id]?.runs.count ?? 0;
                      return (
                        <li key={id} data-lesson={id}>
                          <span>{titleOf(id)}</span>
                          <small>
                            {runs
                              ? t("next.runs", { count: runs })
                              : t("next.noRuns")}
                          </small>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="review-muted">{t("next.none")}</p>
                )}
                {next.status === "available" ? (
                  <Button
                    type="button"
                    data-testid="review-next-open"
                    disabled={studio.running}
                    onClick={() => studio.selectLesson(next.id)}
                  >
                    {t("next.open")}
                    <ArrowRight size={15} aria-hidden="true" />
                  </Button>
                ) : (
                  <p className="review-muted">{t("next.planned")}</p>
                )}
              </>
            )}
          </section>
        </div>
      </LearningBadge>
    </section>
  );
}
