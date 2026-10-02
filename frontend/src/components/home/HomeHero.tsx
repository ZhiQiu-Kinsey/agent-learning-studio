import { useLayoutEffect, useRef, type ReactNode } from "react";
import { animate, useInView } from "motion/react";
import { useTranslation } from "react-i18next";
import { ArrowRight, BookOpen, Compass } from "lucide-react";
import { MotionIntent, useReducedMotion } from "../../motion";
import { Backdrop } from "../backdrops/Backdrop";
import BlurText from "../react-bits/BlurText";
import ShinyText from "../react-bits/ShinyText";
import StarBorder from "../react-bits/StarBorder";
import Magnet from "../react-bits/Magnet";
import ElectricBorder from "../react-bits/ElectricBorder";
import RotatingText from "../react-bits/RotatingText";
import { formatLessonNumber } from "../../lib/lessonIds";
import type { Lesson } from "../../types";
import { useResolvedTheme } from "../../hooks/useTheme";

export interface HeroStat {
  key: "lessons" | "categories" | "available" | "opened" | "runs";
  value: number;
  local?: boolean;
}

/**
 * CountUp for real numbers only: eases from the last shown value (0 at first)
 * once on screen at full motion; static motion and assistive tech get the value.
 */
function StatValue({ value }: { value: number }) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef(0);
  const inView = useInView(ref, { once: true });
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element || reduced) return;
    element.textContent = String(shown.current);
    if (!inView) return;
    const controls = animate(shown.current, value, {
      duration: 1.4,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (latest) => {
        shown.current = Math.round(latest);
        element.textContent = String(shown.current);
      },
    });
    return () => {
      controls.stop();
      shown.current = value;
      element.textContent = String(value);
    };
  }, [inView, reduced, value]);
  return <span ref={ref}>{value}</span>;
}
function PrimaryAction({ children }: { children: ReactNode }) {
  return (
    <Magnet className="home-cta-magnet">
      <StarBorder className="home-cta-star" color="#b98aff" speed="6s">
        {children}
      </StarBorder>
    </Magnet>
  );
}

/** "Continue" exists only when this device really opened a lesson: electric outline. */
function ContinueAction({ children }: { children: ReactNode }) {
  return (
    <Magnet className="home-cta-magnet">
      <span className="home-cta-electric">
        {children}
        <ElectricBorder
          color="#b98aff"
          chaos={0.07}
          speed={0.9}
          borderRadius={14}
        />
      </span>
    </Magnet>
  );
}

/**
 * The observatory band (ink in dark, lavender paper in light): living backdrop, entrance title, the loop in three
 * rotating phrases, the ways in, and catalogue/device numbers that are all real.
 */
export function HomeHero({
  last,
  first,
  stats,
  onOpenLesson,
  onStartOnboarding,
  onOpenMap,
}: {
  last?: Lesson & { shortTitle: string };
  first?: Lesson;
  stats: HeroStat[] | null;
  onOpenLesson: (id: string) => void;
  onStartOnboarding: () => void;
  onOpenMap: () => void;
}) {
  const { t } = useTranslation("home");
  const light = useResolvedTheme() === "light";
  const onboarding = (primary: boolean) => (
    <button
      type="button"
      className={
        primary ? "home-cta home-cta-primary" : "home-cta home-cta-glass"
      }
      data-testid="home-start-onboarding"
      onClick={onStartOnboarding}
    >
      <Compass size={17} aria-hidden="true" />
      {t("startOnboarding")}
      {primary && <ArrowRight size={16} aria-hidden="true" />}
    </button>
  );

  return (
    <section className="home-hero" aria-labelledby="home-hero-title">
      <Backdrop name="lightfall" className="home-hero-backdrop" />
      <div className="home-hero-veil" aria-hidden="true" />
      <div className="home-hero-grid" aria-hidden="true" />
      <div className="home-hero-body">
        <p className="home-kicker">
          <span className="home-kicker-dot" aria-hidden="true" />
          <ShinyText
            text={t("kicker")}
            color={light ? "#4a3bb8" : "#cfc7ff"}
            shineColor={light ? "#b98aff" : "#ffffff"}
            speed={3}
            delay={1.5}
          />
        </p>
        <div id="home-hero-title" className="home-title">
          <MotionIntent
            name="heading.split"
            text={t("title")}
            tag="h1"
            textAlign="left"
            splitType="chars"
            delay={45}
            duration={0.9}
            ease="expo.out"
            from={{ opacity: 0, y: 48, rotateX: -70, filter: "blur(10px)" }}
            to={{ opacity: 1, y: 0, rotateX: 0, filter: "blur(0px)" }}
            rootMargin="0px"
          />
        </div>
        <p className="home-loop">
          <span className="home-loop-label">{t("hero.loopLabel")}</span>
          <RotatingText
            className="home-loop-pill"
            texts={[t("hero.loop1"), t("hero.loop2"), t("hero.loop3")]}
            separator=" → "
          />
        </p>
        <p className="home-lead">
          <BlurText text={t("lead")} delay={10} />
        </p>
        <div className="home-actions">
          {last ? (
            <ContinueAction>
              <button
                type="button"
                className="home-cta home-cta-primary"
                data-testid="home-continue"
                onClick={() => onOpenLesson(last.id)}
              >
                <BookOpen size={17} aria-hidden="true" />
                {t("continue", {
                  number: formatLessonNumber(last.number),
                  title: last.shortTitle,
                })}
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            </ContinueAction>
          ) : (
            <PrimaryAction>{onboarding(true)}</PrimaryAction>
          )}
          {last
            ? onboarding(false)
            : first && (
                <button
                  type="button"
                  className="home-cta home-cta-glass"
                  data-testid="home-first-lesson"
                  onClick={() => onOpenLesson(first.id)}
                >
                  <BookOpen size={17} aria-hidden="true" />
                  {t("firstLesson")}
                </button>
              )}
          {/* Tertiary: a text link, so the three ways in read as one clear
              primary, one glass secondary and a quiet link. */}
          <button
            type="button"
            className="home-cta home-cta-link"
            data-testid="home-map"
            onClick={onOpenMap}
          >
            <span>{t("map")}</span>
            <ArrowRight size={15} aria-hidden="true" />
          </button>
        </div>
      </div>
      {stats && (
        <div className="home-stats-wrap">
          <dl className="home-stats" aria-label={t("stats.label")}>
            {stats.map((stat) => (
              <div
                key={stat.key}
                className={`home-stat ${stat.local ? "is-local" : ""}`}
              >
                <dt>{t(`stats.${stat.key}`)}</dt>
                <dd>
                  <StatValue value={stat.value} />
                </dd>
              </div>
            ))}
          </dl>
          <p className="home-stats-source">{t("stats.source")}</p>
        </div>
      )}
    </section>
  );
}
