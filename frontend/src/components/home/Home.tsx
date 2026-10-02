import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, BookOpen, Compass, Map as MapIcon } from "lucide-react";
import { jsonFetch } from "../../api";
import { MotionIntent } from "../../motion";
import { onboardingProgressId, useProgress } from "../../progress";
import { blocksOfType, sceneBlocks } from "../../content/view";
import { IllustrationFlow } from "../../content/blocks/IllustrationFlow";
import type { Onboarding } from "../../content/types.gen";
import type { CurriculumData, Lesson } from "../../types";
import { formatLessonNumber } from "../../lib/lessonIds";
import { Button } from "../ui/button";
import "../../styles/home.css";

const stripNumber = (title: string) =>
  title.replace(/^第\s*\d+\s*课[：:]?\s*/, "");

/**
 * Home: one illustrated Agent loop (clearly labelled as an illustration), the
 * learning journey with this device's real progress, and a way back in.
 */
export function Home({
  lessons,
  onOpenLesson,
  onStartOnboarding,
  onOpenMap,
}: {
  lessons: Lesson[];
  onOpenLesson: (id: string) => void;
  onStartOnboarding: () => void;
  onOpenMap: () => void;
}) {
  const { t } = useTranslation("home");
  const progress = useProgress();
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    jsonFetch<Onboarding>("/api/onboarding", { signal: abort.signal })
      .then((value) => !abort.signal.aborted && setOnboarding(value))
      .catch(() => undefined);
    jsonFetch<CurriculumData>("/api/curriculum", { signal: abort.signal })
      .then((value) => !abort.signal.aborted && setCurriculum(value))
      .catch(() => undefined);
    return () => abort.abort();
  }, []);

  const last = lessons.find(
    (lesson) => lesson.id === progress.lastLessonId && lesson.available,
  );
  const first = lessons.find((lesson) => lesson.available);
  const flow = onboarding?.chapters
    .map((chapter) => ({
      chapter,
      block: blocksOfType(sceneBlocks(chapter, "understand"), "flow")[0],
    }))
    .find(
      (item) =>
        item.block && item.chapter.illustrations[item.block.illustration],
    );
  const checkpoints = Object.keys(
    progress.lessons[onboardingProgressId]?.checkpoints ?? {},
  ).length;

  return (
    <div className="home-page" data-testid="home-page">
      <section className="home-hero">
        <p className="home-kicker">{t("kicker")}</p>
        <MotionIntent
          name="heading.split"
          text={t("title")}
          tag="h1"
          textAlign="left"
          splitType="chars"
          delay={30}
          duration={0.5}
          from={{ opacity: 0, y: 12 }}
          to={{ opacity: 1, y: 0 }}
          rootMargin="0px"
        />
        <p className="home-lead">{t("lead")}</p>
        <div className="home-actions">
          {last ? (
            <Button
              data-testid="home-continue"
              onClick={() => onOpenLesson(last.id)}
            >
              {t("continue", {
                number: formatLessonNumber(last.number),
                title: stripNumber(last.title),
              })}
              <ArrowRight size={16} />
            </Button>
          ) : (
            <Button
              data-testid="home-start-onboarding"
              onClick={onStartOnboarding}
            >
              <Compass size={16} />
              {t("startOnboarding")}
            </Button>
          )}
          {last ? (
            <Button
              variant="outline"
              data-testid="home-start-onboarding"
              onClick={onStartOnboarding}
            >
              <Compass size={16} />
              {t("startOnboarding")}
            </Button>
          ) : (
            first && (
              <Button
                variant="outline"
                data-testid="home-first-lesson"
                onClick={() => onOpenLesson(first.id)}
              >
                <BookOpen size={16} />
                {t("firstLesson")}
              </Button>
            )
          )}
          <Button variant="ghost" data-testid="home-map" onClick={onOpenMap}>
            <MapIcon size={16} />
            {t("map")}
          </Button>
        </div>
      </section>
      {flow?.block && (
        <section className="home-stage" aria-label={t("stageTitle")}>
          <h2>{t("stageTitle")}</h2>
          <IllustrationFlow
            block={flow.block}
            illustration={flow.chapter.illustrations[flow.block.illustration]}
          />
        </section>
      )}
      <section
        className="home-journey"
        aria-label={t("journey.title")}
        data-testid="home-journey"
      >
        <h2>{t("journey.title")}</h2>
        <ol>
          <li>
            <button type="button" onClick={onStartOnboarding}>
              <strong>{t("journey.chapter0")}</strong>
              <span>{t("journey.chapter0Help")}</span>
              <small>{t("journey.checkpoints", { count: checkpoints })}</small>
            </button>
          </li>
          {curriculum?.categories.map((category) => {
            const ids = new Set(
              category.modules.flatMap((module) => module.lesson_ids),
            );
            const inCategory = curriculum.lessons.filter((lesson) =>
              ids.has(lesson.id),
            );
            const available = inCategory.filter(
              (lesson) => lesson.status === "available",
            );
            const opened = inCategory.filter(
              (lesson) => progress.lessons[lesson.id],
            ).length;
            const runs = inCategory.reduce(
              (sum, lesson) =>
                sum + (progress.lessons[lesson.id]?.runs.count ?? 0),
              0,
            );
            const target =
              available.find((lesson) => !progress.lessons[lesson.id]) ??
              available[0];
            return (
              <li key={category.id} data-testid="home-journey-category">
                <button
                  type="button"
                  disabled={!target}
                  onClick={() => (target ? onOpenLesson(target.id) : undefined)}
                >
                  <strong>{category.title}</strong>
                  <span>{category.description}</span>
                  <small>
                    {t("journey.available", { count: available.length })} ·{" "}
                    {t("journey.planned", {
                      count: inCategory.length - available.length,
                    })}
                  </small>
                  {(opened > 0 || runs > 0) && (
                    <small className="home-progress">
                      {t("journey.opened", { count: opened })} ·{" "}
                      {t("journey.runs", { count: runs })}
                    </small>
                  )}
                </button>
              </li>
            );
          })}
        </ol>
        <p className="home-honesty">{t("honesty")}</p>
      </section>
    </div>
  );
}
