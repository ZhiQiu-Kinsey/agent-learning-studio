import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { Check, CheckCheck } from "lucide-react";
import { useReducedMotion } from "../../motion";
import { onboardingProgressId, track } from "../../progress";
import SpringCheck from "../react-bits/SpringCheck";
import type { ChapterContent, CheckedPoints } from "./chapters";
import { Reveal } from "./Reveal";

/** End-of-chapter pause: self-reported checkpoints stored in this browser. */
export function ChapterExercise({
  chapter,
  checked,
  done,
}: {
  chapter: ChapterContent;
  checked: CheckedPoints;
  /** Every checkpoint of this chapter is ticked. */
  done: boolean;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const reduced = useReducedMotion();
  return (
    <Reveal
      as="section"
      className="onboarding-exercise"
      data-complete={done ? "true" : "false"}
    >
      <div className="onboarding-exercise-head">
        <span className="onboarding-eyebrow">
          <CheckCheck size={15} aria-hidden="true" />
          {t("pause")}
        </span>
        <AnimatePresence>
          {done && (
            <motion.span
              className="onboarding-exercise-badge"
              initial={reduced ? false : { opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={reduced ? undefined : { opacity: 0, scale: 0.8 }}
              transition={
                reduced
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 500, damping: 22 }
              }
            >
              <Check size={13} aria-hidden="true" />
              {t("chapterChecked")}
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <h3>{chapter.exercise.title}</h3>
      <p>{chapter.exercise.prompt}</p>
      <div className="onboarding-checks" data-testid="onboarding-checks">
        {chapter.exercise.checkpoints.map((point) => {
          const id = `${chapter.id}/${point.id}`;
          return (
            <SpringCheck
              key={id}
              className="onboarding-check"
              label={point.text}
              checked={!!checked[id]}
              onChange={(value) =>
                track.checkpointSet(onboardingProgressId, id, value)
              }
            />
          );
        })}
      </div>
      <small>{t("checkNote")}</small>
    </Reveal>
  );
}
