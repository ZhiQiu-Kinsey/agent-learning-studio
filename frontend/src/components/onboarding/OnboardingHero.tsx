import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  ArrowRight,
  BookOpen,
  CheckCheck,
  Clock3,
  Layers3,
  Sparkles,
} from "lucide-react";
import { useMotionBudget, useReducedMotion } from "../../motion";
import type { Onboarding } from "../../content/types.gen";
import { Button } from "../ui/button";
import SplitText from "../react-bits/SplitText";
import ShinyText from "../react-bits/ShinyText";
import StarBorder from "../react-bits/StarBorder";
import { Backdrop } from "../backdrops/Backdrop";
import { easeOut } from "./transitions";

/** Orbiting model / tool / evidence diagram beside the hero copy (decorative). */
function HeroOrbit() {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  return (
    <div className="onboarding-orbit" aria-hidden="true">
      <div className="orbit-ring orbit-ring-one" />
      <div className="orbit-ring orbit-ring-two" />
      <div className="orbit-ring orbit-ring-three" />
      <div className="onboarding-orb">
        <Backdrop name="orb" className="onboarding-orb-shader is-interactive" />
      </div>
      <div className="orbit-core">
        <span>{t("core")}</span>
        <small>{t("coreTagline")}</small>
      </div>
      <span className="orbit-label orbit-label-a">{t("orbitModel")}</span>
      <span className="orbit-label orbit-label-b">{t("orbitTool")}</span>
      <span className="orbit-label orbit-label-c">{t("orbitEvidence")}</span>
      <i className="orbit-signal" />
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
  // CSS orbit loops run only while the hero is on screen in a visible tab.
  const { ref, active } = useMotionBudget<HTMLElement>("css");
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
    <section
      ref={ref}
      data-testid="onboarding-hero"
      className={`onboarding-hero ${active ? "is-animating" : ""}`}
    >
      <div className="onboarding-hero-grid" aria-hidden="true" />
      <div className="onboarding-hero-copy">
        <motion.span className="onboarding-eyebrow" {...rise(-1)}>
          <Sparkles size={13} aria-hidden="true" />
          <ShinyText
            text={t("eyebrow")}
            speed={4}
            delay={2}
            disabled={!!reduced}
            color="#8ff0de"
            shineColor="#ffffff"
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
          <StarBorder
            className="onboarding-start-star"
            color="#49dec6"
            speed="6s"
          >
            <Button
              className="onboarding-start-button"
              onClick={() =>
                document
                  .getElementById("onboarding-chapter")
                  ?.scrollIntoView({ behavior: reduced ? "instant" : "smooth" })
              }
            >
              {t("start")} <ArrowRight size={16} />
            </Button>
          </StarBorder>
          <Button
            variant="ghost"
            className="onboarding-map-button"
            onClick={onMap}
          >
            <Layers3 size={15} />
            {t("explore")}
          </Button>
        </motion.div>
        <motion.div
          className="onboarding-meta"
          data-testid="onboarding-meta"
          {...rise(3)}
        >
          <span>
            <BookOpen size={14} />
            {t("metaChapters", { n: content.chapters.length })}
          </span>
          <span>
            <Clock3 size={14} />
            {t("metaMinutes", { n: minutes })}
          </span>
          <span>
            <CheckCheck size={14} />
            {t("metaChecked", { n: completed })}
          </span>
        </motion.div>
      </div>
      <HeroOrbit />
    </section>
  );
}
