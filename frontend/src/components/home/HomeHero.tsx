import { useLayoutEffect, useRef } from "react";
import { animate, motion, useInView } from "motion/react";
import { useTranslation } from "react-i18next";
import { ArrowRight } from "lucide-react";
import {
  revealProps,
  useBeat,
  useMotionBudget,
  useReducedMotion,
} from "../../motion";
import { Backdrop } from "../backdrops/Backdrop";
import ShinyText from "../react-bits/ShinyText";
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

/** The illustrated trace: two rounds of one loop (example values, not a run). */
const TRACE: {
  round?: number;
  who?: "request" | "model" | "python";
  code?: string;
  value?: string;
  note?: "toModel" | "toNextRound";
}[] = [
  { round: 1 },
  { who: "request", code: "messages + tools", note: "toModel" },
  { who: "model", code: "tool_calls: ", value: "add_numbers(19, 23)" },
  { who: "python", code: "tool_result: ", value: "42" },
  { round: 2 },
  { who: "request", code: "role=tool", note: "toNextRound" },
  { who: "model", code: "answer: 19 + 23 = ", value: "42" },
];
const TRACE_ROWS = TRACE.filter((item) => item.who).length;

/**
 * The observatory band: living backdrop, a two-line title with an accent,
 * the loop as three phrases that light up in turn, the ways in as an arrow
 * link plus two quiet links, an illustrated trace card, and real numbers.
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
  const { ref, active, reduced } = useMotionBudget<HTMLDivElement>();
  const beat = useBeat(active);
  // Static motion shows the whole loop at once rather than a frozen frame.
  const still = reduced;
  const phrase = beat % 3;
  const traceStep = beat % (TRACE_ROWS + 1);
  const phrases = [t("hero.loop1"), t("hero.loop2"), t("hero.loop3")];

  const primary = last
    ? {
        testId: "home-continue",
        label: t("continue", {
          number: formatLessonNumber(last.number),
          title: last.shortTitle,
        }),
        onClick: () => onOpenLesson(last.id),
      }
    : {
        testId: "home-start-onboarding",
        label: t("startOnboarding"),
        onClick: onStartOnboarding,
      };
  const secondary = last
    ? {
        testId: "home-start-onboarding",
        label: t("startOnboarding"),
        onClick: onStartOnboarding,
      }
    : first && {
        testId: "home-first-lesson",
        label: t("firstLesson"),
        onClick: () => onOpenLesson(first.id),
      };

  let row = -1;
  return (
    <section className="home-hero" aria-labelledby="home-hero-title">
      <Backdrop name="lightfall" className="home-hero-backdrop" />
      <div className="home-hero-veil" aria-hidden="true" />
      <div className="home-hero-grid" aria-hidden="true" />
      <div className="home-hero-main" ref={ref}>
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
          <motion.h1
            id="home-hero-title"
            className="home-title"
            {...revealProps(
              reduced,
              { opacity: 0, y: 28, filter: "blur(10px)" },
              { opacity: 1, y: 0, filter: "blur(0px)" },
              { duration: 0.9, ease: [0.16, 1, 0.3, 1] },
            )}
          >
            {t("hero.titleLead")}
            <br />
            <span className="home-title-accent">{t("hero.titleAccent")}</span>
            {t("hero.titleTail")}
          </motion.h1>
          <p className="home-loop">
            <span className="home-loop-label">{t("hero.loopLabel")}</span>
            {phrases.map((text, index) => (
              <span key={index} className="home-loop-step-wrap">
                {index > 0 && (
                  <span className="home-loop-arrow" aria-hidden="true">
                    →
                  </span>
                )}
                <span
                  className="home-loop-step"
                  data-lit={still || index === phrase ? "" : undefined}
                >
                  {text}
                </span>
              </span>
            ))}
          </p>
          <div className="home-actions">
            <button
              type="button"
              className="home-go"
              data-testid={primary.testId}
              onClick={primary.onClick}
            >
              <span className="home-go-ring" aria-hidden="true">
                <ArrowRight size={20} />
              </span>
              <span className="home-go-text">{primary.label}</span>
            </button>
            <span className="home-entry-links">
              {secondary && (
                <button
                  type="button"
                  className="home-entry-minor"
                  data-testid={secondary.testId}
                  onClick={secondary.onClick}
                >
                  {secondary.label}
                </button>
              )}
              <button
                type="button"
                className="home-cta home-cta-link"
                data-testid="home-map"
                onClick={onOpenMap}
              >
                <span>{t("map")}</span>
                <ArrowRight size={15} aria-hidden="true" />
              </button>
            </span>
          </div>
        </div>
        <figure
          className="home-trace"
          role="img"
          aria-label={t("hero.trace.label")}
        >
          <header aria-hidden="true">
            <span className="home-trace-dots">
              <i />
              <i />
              <i />
            </span>
            <span className="home-trace-title">agent-loop.trace</span>
            <span className="home-trace-tag">{t("stage.badge")}</span>
          </header>
          <ol aria-hidden="true">
            {TRACE.map((item, index) => {
              if (item.round)
                return (
                  <li key={index} className="home-trace-round">
                    {t("hero.trace.round", { number: item.round })}
                  </li>
                );
              row += 1;
              const state =
                still || row < traceStep
                  ? "done"
                  : row === traceStep
                    ? "now"
                    : undefined;
              return (
                <li key={index} className="home-trace-row" data-state={state}>
                  <span className="home-trace-who" data-who={item.who}>
                    {item.who}
                  </span>
                  <span className="home-trace-what">
                    {item.code}
                    {item.value && <b>{item.value}</b>}
                    {item.note && <em> {t(`hero.trace.${item.note}`)}</em>}
                  </span>
                </li>
              );
            })}
          </ol>
        </figure>
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
