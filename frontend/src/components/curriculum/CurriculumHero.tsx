import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  ArrowUpRight,
  BookOpen,
  CircleCheckBig,
  Compass,
  Layers3,
  Route,
} from "lucide-react";
import { useReducedMotion } from "../../motion";
import type { ProgressRecord } from "../../progress";
import type { CurriculumData } from "../../types";
import { Button } from "../ui/button";
import BlurText from "../react-bits/BlurText";
import StarBorder from "../react-bits/StarBorder";
import { Backdrop } from "../backdrops/Backdrop";
import { MapMetric } from "./MapMetric";
import { easeOut } from "./transitions";

/** Hero entrance: blur-in from below, staggered by `step`. */
function HeroReveal({
  step,
  className,
  children,
}: {
  step: number;
  className?: string;
  children: ReactNode;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y: 18, filter: "blur(10px)" }}
      animate={{
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        transitionEnd: { filter: "none" },
      }}
      transition={{ duration: 0.7, delay: 0.1 + step * 0.09, ease: easeOut }}
    >
      {children}
    </motion.div>
  );
}

/** Map masthead: title, resume/start action, route shortcut and real counts. */
export function CurriculumHero({
  curriculum,
  progress,
  onSelectLesson,
  onShowRoute,
}: {
  curriculum: CurriculumData;
  progress: ProgressRecord;
  onSelectLesson: (id: string) => void;
  onShowRoute: () => void;
}) {
  const { t } = useTranslation("curriculum");
  const availableCount = curriculum.lessons.filter(
    (lesson) => lesson.status === "available",
  ).length;
  const moduleCount = curriculum.categories.reduce(
    (sum, category) => sum + category.modules.length,
    0,
  );
  const lastLesson = curriculum.lessons.find(
    (lesson) =>
      lesson.status === "available" &&
      progress.lastLessonId &&
      (lesson.id === progress.lastLessonId ||
        lesson.aliases?.includes(progress.lastLessonId)),
  );
  const firstAvailable = curriculum.lessons.find(
    (lesson) => lesson.status === "available",
  );
  const target = lastLesson ?? firstAvailable;

  return (
    <header
      className="curriculum-map-header curriculum-hero"
      aria-labelledby="curriculum-title"
    >
      <Backdrop name="topography" className="curriculum-hero-backdrop" />
      <div className="curriculum-hero-scrim" aria-hidden="true" />
      <div className="curriculum-map-copy">
        <HeroReveal step={0}>
          <span className="curriculum-eyebrow">
            <Compass size={15} aria-hidden="true" />
            {t("eyebrow", { version: curriculum.version })}
          </span>
        </HeroReveal>
        <h1 id="curriculum-title" data-testid="curriculum-title">
          <BlurText text={t("title")} delay={90} />
        </h1>
        <HeroReveal step={2}>
          <p className="curriculum-hero-description">
            {t("description", { title: curriculum.title })}
          </p>
        </HeroReveal>
        <HeroReveal step={3} className="curriculum-hero-actions">
          {target && (
            <StarBorder
              className="curriculum-start-star"
              color="#49dec6"
              speed="6s"
            >
              <Button
                className="curriculum-start-button"
                onClick={() => onSelectLesson(target.id)}
              >
                {lastLesson
                  ? t("resume", { number: lastLesson.number })
                  : t("start", { number: target.number })}
                <ArrowUpRight size={16} />
              </Button>
            </StarBorder>
          )}
          <Button
            variant="ghost"
            className="curriculum-hero-route"
            onClick={onShowRoute}
          >
            <Route size={15} aria-hidden="true" />
            {t("hero.route")}
          </Button>
        </HeroReveal>
      </div>
      <div className="curriculum-stats" aria-label={t("stats.label")}>
        <MapMetric
          value={curriculum.categories.length}
          label={t("stats.domains")}
          index={0}
          Icon={Compass}
        />
        <MapMetric
          value={moduleCount}
          label={t("stats.modules")}
          index={1}
          Icon={Layers3}
        />
        <MapMetric
          value={curriculum.lessons.length}
          label={t("stats.lessons")}
          index={2}
          Icon={BookOpen}
        />
        <MapMetric
          value={availableCount}
          label={t("stats.available")}
          index={3}
          Icon={CircleCheckBig}
          ratio={
            curriculum.lessons.length
              ? availableCount / curriculum.lessons.length
              : 0
          }
        />
      </div>
    </header>
  );
}
