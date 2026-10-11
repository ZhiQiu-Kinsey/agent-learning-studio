import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  ArrowRight,
  BookOpen,
  CheckCheck,
  Clock3,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { useBeat, useMotionBudget, useReducedMotion } from "../../motion";
import type { Onboarding } from "../../content/types.gen";
import SplitText from "../react-bits/SplitText";
import ShinyText from "../react-bits/ShinyText";
import { useResolvedTheme } from "../../hooks/useTheme";
import { easeOut } from "./transitions";

const LOOP = ["predict", "run", "check", "explain"] as const;

/**
 * The learning loop every lesson uses, four cards lit in turn on screen at
 * full motion; static motion lights all four.
 */
function HeroLoop() {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding.loop" });
  const { ref, active, reduced } = useMotionBudget<HTMLDivElement>();
  const lit = useBeat(active) % LOOP.length;
  return (
    <div className="onboarding-loop" ref={ref}>
      <p className="onboarding-loop-title">{t("title")}</p>
      <ol>
        {LOOP.map((step, index) => (
          <li
            key={step}
            data-state={
              reduced
                ? "lit"
                : index === lit
                  ? "lit"
                  : index < lit
                    ? "done"
                    : "next"
            }
          >
            <strong>{t(step)}</strong>
            <span>{t(`${step}Hint`)}</span>
          </li>
        ))}
      </ol>
      <p className="onboarding-loop-again">
        <RotateCcw size={12} aria-hidden="true" />
        {t("again")}
      </p>
    </div>
  );
}

export function OnboardingHero({
  content,
  completed,
  onMap,
}: {
  content: Onboarding;
  completed: number;
  onMap: () => void;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const reduced = useReducedMotion();
  const dark = useResolvedTheme() === "dark";
  const minutes = content.chapters.reduce(
    (sum, item) => sum + item.estimated_minutes,
    0,
  );
  const rise = (step: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: 16, filter: "blur(8px)" },
          animate: {
            opacity: 1,
            y: 0,
            filter: "blur(0px)",
            transitionEnd: { filter: "none" },
          },
          transition: {
            duration: 0.7,
            delay: 0.25 + step * 0.1,
            ease: easeOut,
          },
        };
  return (
    <section data-testid="onboarding-hero" className="onboarding-hero">
      <div className="onboarding-hero-grid" aria-hidden="true" />
      <div className="onboarding-hero-copy">
        <motion.span className="onboarding-eyebrow" {...rise(-1)}>
          <Sparkles size={13} aria-hidden="true" />
          <ShinyText
            text={t("eyebrow")}
            speed={4}
            delay={2}
            disabled={!!reduced}
            color={dark ? "#8ff0de" : "#0a6a62"}
            shineColor={dark ? "#ffffff" : "#6d5dfc"}
          />
        </motion.span>
        {reduced ? (
          <h1>{t("title")}</h1>
        ) : (
          <SplitText
            text={t("title")}
            tag="h1"
            splitType="chars"
            textAlign="left"
            delay={35}
            duration={0.65}
            from={{ opacity: 0, y: 25, rotateX: -35 }}
            to={{ opacity: 1, y: 0, rotateX: 0 }}
          />
        )}
        <motion.p {...rise(1)}>{content.description}</motion.p>
        <motion.div className="onboarding-hero-actions" {...rise(2)}>
          <button
            type="button"
            className="onboarding-go"
            onClick={() =>
              document
                .getElementById("onboarding-chapter")
                ?.scrollIntoView({ behavior: reduced ? "instant" : "smooth" })
            }
          >
            <span className="onboarding-go-ring" aria-hidden="true">
              <ArrowRight size={17} />
            </span>
            <span className="onboarding-go-text">{t("start")}</span>
          </button>
          <button type="button" className="onboarding-map-link" onClick={onMap}>
            {t("explore")}
            <ArrowRight size={14} aria-hidden="true" />
          </button>
        </motion.div>
        <motion.div
          className="onboarding-meta"
          data-testid="onboarding-meta"
          {...rise(3)}
        >
          <span>
            <BookOpen size={14} />
            {t("metaChapters", { count: content.chapters.length })}
          </span>
          <span>
            <Clock3 size={14} />
            {t("metaMinutes", { count: minutes })}
          </span>
          <span>
            <CheckCheck size={14} />
            {t("metaChecked", { count: completed })}
          </span>
        </motion.div>
      </div>
      <motion.div className="onboarding-hero-side" {...rise(2)}>
        <HeroLoop />
      </motion.div>
    </section>
  );
}
