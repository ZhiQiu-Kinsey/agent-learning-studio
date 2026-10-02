import { useEffect, useMemo, useState } from "react";
import { jsonFetch } from "../../api";
import { useProgress } from "../../progress";
import { useCurriculum } from "../../hooks/useCurriculum";
import { blocksOfType, sceneBlocks } from "../../content/view";
import type { Onboarding } from "../../content/types.gen";
import type { Lesson } from "../../types";
import { HomeHero, type HeroStat } from "./HomeHero";
import { HomeStage } from "./HomeStage";
import { HomeTopics } from "./HomeTopics";
import { HomeMethod } from "./HomeMethod";
import { HomeJourney } from "./HomeJourney";
import "../../styles/home.css";

const stripNumber = (title: string) =>
  title.replace(/^第\s*\d+\s*课[：:]?\s*/, "");

/**
 * Home: a dark observatory hero with real catalogue and device numbers, the
 * illustrated Agent loop (clearly labelled, stepped by hand), the topics and
 * rhythm of the course, and the learning journey with this device's progress.
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
  const progress = useProgress();
  const curriculum = useCurriculum();
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    jsonFetch<Onboarding>("/api/onboarding", { signal: abort.signal })
      .then((value) => !abort.signal.aborted && setOnboarding(value))
      .catch(() => undefined);
    return () => abort.abort();
  }, []);

  const lastLesson = lessons.find(
    (lesson) => lesson.id === progress.lastLessonId && lesson.available,
  );
  const last = lastLesson && {
    ...lastLesson,
    shortTitle: stripNumber(lastLesson.title),
  };
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

  const stats = useMemo<HeroStat[] | null>(() => {
    if (!curriculum) return null;
    const ids = new Set(curriculum.lessons.map((lesson) => lesson.id));
    const visited = Object.entries(progress.lessons).filter(([id]) =>
      ids.has(id),
    );
    return [
      { key: "lessons", value: curriculum.lessons.length },
      { key: "categories", value: curriculum.categories.length },
      {
        key: "available",
        value: curriculum.lessons.filter(
          (lesson) => lesson.status === "available",
        ).length,
      },
      { key: "opened", value: visited.length, local: true },
      {
        key: "runs",
        value: visited.reduce((sum, [, entry]) => sum + entry.runs.count, 0),
        local: true,
      },
    ];
  }, [curriculum, progress.lessons]);

  return (
    <div className="home-page" data-testid="home-page">
      <HomeHero
        last={last}
        first={first}
        stats={stats}
        onOpenLesson={onOpenLesson}
        onStartOnboarding={onStartOnboarding}
        onOpenMap={onOpenMap}
      />
      {flow?.block && (
        <HomeStage
          block={flow.block}
          illustration={flow.chapter.illustrations[flow.block.illustration]}
        />
      )}
      <HomeMethod />
      {curriculum && <HomeTopics curriculum={curriculum} />}
      <HomeJourney
        curriculum={curriculum}
        onOpenLesson={onOpenLesson}
        onStartOnboarding={onStartOnboarding}
      />
    </div>
  );
}
