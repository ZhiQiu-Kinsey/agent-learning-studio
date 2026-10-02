import type { CSSProperties } from "react";
import { motion } from "motion/react";
import { useReducedMotion } from "../../motion";
import type { Chapter } from "../../content/types.gen";
import { GlossaryScope } from "../../content/glossary/Glossary";
import { backdropAccent } from "../curriculum/atmosphere";
import { ChapterBand } from "./ChapterBand";
import { ChapterExercise } from "./ChapterExercise";
import { ChapterFooter } from "./ChapterFooter";
import { ChapterSection } from "./ChapterSection";
import {
  chapterChecks,
  skyFor,
  type ChapterContent,
  type CheckedPoints,
} from "./chapters";
import { easeOut } from "./transitions";

/**
 * The current chapter: sky band, reading sections, checkpoints and footer.
 * Render inside `<AnimatePresence mode="wait">` keyed by chapter id; it slides
 * in from the side given by `direction` (+1 forward, -1 back).
 */
export function ChapterArticle({
  chapter,
  chapters,
  index,
  direction,
  checked,
  onNavigate,
  onStart,
}: {
  chapter: ChapterContent;
  chapters: Chapter[];
  index: number;
  direction: number;
  checked: CheckedPoints;
  onNavigate: (index: number) => void;
  onStart: () => void;
}) {
  const reduced = useReducedMotion();
  const sky = skyFor(chapter.id, index);
  const checks = chapterChecks(chapter, checked);
  const glossaryTexts = chapter.sections.flatMap((section) => [
    ...section.paragraphs,
    ...(section.bullets ?? []),
    ...(section.table?.rows.flat() ?? []),
  ]);
  const offset = 46 * direction;
  return (
    <motion.article
      className="onboarding-chapter"
      data-testid="onboarding-chapter"
      style={{ "--chapter-rgb": backdropAccent(sky) } as CSSProperties}
      initial={
        reduced ? false : { opacity: 0, x: offset, filter: "blur(14px)" }
      }
      animate={{
        opacity: 1,
        x: 0,
        filter: "blur(0px)",
        transitionEnd: { filter: "none" },
      }}
      exit={
        reduced
          ? {}
          : {
              opacity: 0,
              x: -offset * 0.6,
              filter: "blur(10px)",
              transition: { duration: 0.22, ease: [0.4, 0, 1, 1] },
            }
      }
      transition={{ duration: 0.5, ease: easeOut }}
    >
      <ChapterBand
        chapter={chapter}
        index={index}
        total={chapters.length}
        sky={sky}
      />
      <GlossaryScope texts={glossaryTexts}>
        <div className="onboarding-chapter-body">
          {chapter.sections.map((section, sectionIndex) => (
            <ChapterSection
              key={section.id}
              chapter={chapter}
              section={section}
              index={sectionIndex}
            />
          ))}
          <ChapterExercise
            chapter={chapter}
            checked={checked}
            done={checks.total > 0 && checks.done === checks.total}
          />
          <ChapterFooter
            chapter={chapter}
            chapters={chapters}
            index={index}
            onNavigate={onNavigate}
            onStart={onStart}
          />
        </div>
      </GlossaryScope>
    </motion.article>
  );
}
