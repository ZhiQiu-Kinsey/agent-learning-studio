import { useEffect, useRef } from "react";
import { AnimatePresence } from "motion/react";
import { useReducedMotion } from "../motion";
import { onboardingProgressId, useProgress } from "../progress";
import { ChapterArticle } from "./onboarding/ChapterArticle";
import { ChapterTabs } from "./onboarding/ChapterTabs";
import { chapterChecks, readChapter } from "./onboarding/chapters";
import { ObjectivesAside } from "./onboarding/ObjectivesAside";
import { OnboardingHero } from "./onboarding/OnboardingHero";
import { OnboardingLoading } from "./onboarding/OnboardingLoading";
import { useOnboardingContent } from "./onboarding/useOnboardingContent";

/** Chapter 0: hero, chapter tabs, the current chapter and its objectives. */
export function Onboarding({
  chapter,
  onChapterChange,
  onStart,
  onMap,
}: {
  chapter: number;
  onChapterChange: (index: number) => void;
  onStart: () => void;
  onMap: () => void;
}) {
  const { content, error, retry } = useOnboardingContent();
  // Self-reported checkpoints persist locally; they are not a score.
  const checked =
    useProgress().lessons[onboardingProgressId]?.checkpoints ?? {};
  const reduced = useReducedMotion();
  // Direction of the last chapter change, for the slide of the transition.
  const previous = useRef(chapter);
  const direction = chapter >= previous.current ? 1 : -1;
  useEffect(() => {
    previous.current = chapter;
  }, [chapter]);

  if (!content) return <OnboardingLoading error={error} onRetry={retry} />;

  const chapterIndex = content.chapters[chapter] ? chapter : 0;
  const current = readChapter(content.chapters[chapterIndex]);
  const completed = content.chapters.filter((item) => {
    const { done, total } = chapterChecks(item, checked);
    return done === total;
  }).length;
  function navigate(index: number) {
    onChapterChange(index);
    window.scrollTo({ top: 0, behavior: reduced ? "instant" : "smooth" });
  }

  return (
    <div className="onboarding-page" data-testid="onboarding-page">
      <OnboardingHero content={content} completed={completed} onMap={onMap} />
      <ChapterTabs
        chapters={content.chapters}
        activeIndex={chapterIndex}
        checked={checked}
        onNavigate={navigate}
      />
      <div className="onboarding-reading-layout" id="onboarding-chapter">
        <AnimatePresence mode="wait" initial={false}>
          <ChapterArticle
            key={current.id}
            chapter={current}
            chapters={content.chapters}
            index={chapterIndex}
            direction={direction}
            checked={checked}
            onNavigate={navigate}
            onStart={onStart}
          />
        </AnimatePresence>
        <ObjectivesAside chapter={current} onStart={onStart} />
      </div>
    </div>
  );
}
