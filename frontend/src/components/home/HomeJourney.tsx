import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { ArrowUpRight, Compass } from "lucide-react";
import { revealProps, useReducedMotion } from "../../motion";
import { onboardingProgressId, useProgress } from "../../progress";
import SpotlightCard from "../react-bits/SpotlightCard";
import type { CurriculumData } from "../../types";
import { rgbChannels } from "../../lib/color";
import { categoryTint } from "./tint";
import Shuffle from "../react-bits/Shuffle";

function Reveal({
  index,
  children,
  ...rest
}: {
  index: number;
  children: ReactNode;
  style?: CSSProperties;
  "data-testid"?: string;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.li
      {...rest}
      {...revealProps(
        reduced,
        { opacity: 0, y: 36, scale: 0.96 },
        { opacity: 1, y: 0, scale: 1 },
        {
          type: "spring",
          damping: 22,
          stiffness: 160,
          delay: (index % 4) * 0.07,
        },
      )}
      viewport={{ once: true, amount: 0.15 }}
    >
      {children}
    </motion.li>
  );
}

/**
 * Domain cards in the colours of their lesson bands. Every count is either from
 * the catalogue or from this device's progress store.
 */
export function HomeJourney({
  curriculum,
  onOpenLesson,
  onStartOnboarding,
}: {
  curriculum: CurriculumData | null;
  onOpenLesson: (id: string) => void;
  onStartOnboarding: () => void;
}) {
  const { t } = useTranslation("home");
  const progress = useProgress();
  const checkpoints = Object.keys(
    progress.lessons[onboardingProgressId]?.checkpoints ?? {},
  ).length;

  return (
    <section
      className="home-section home-journey"
      aria-labelledby="home-journey-title"
      data-testid="home-journey"
    >
      <header className="home-section-head">
        <p className="home-eyebrow">
          <Shuffle text={t("journey.kicker")} />
        </p>
        <h2 id="home-journey-title">{t("journey.title")}</h2>
        <p>{t("journey.lead")}</p>
      </header>
      <ol className="home-domains">
        <Reveal
          index={0}
          style={
            { "--tint": "#49dec6", "--tint-rgb": "73 222 198" } as CSSProperties
          }
        >
          <SpotlightCard
            className="home-domain is-prelude"
            spotlightColor="rgba(73, 222, 198, 0.2)"
          >
            <button
              type="button"
              className="home-domain-button"
              onClick={onStartOnboarding}
            >
              <span
                className="home-domain-sky"
                aria-hidden="true"
                style={{ background: categoryTint("H").sky }}
              >
                <span className="home-domain-letter">0</span>
                <Compass className="home-domain-icon" size={20} />
              </span>
              <span className="home-domain-body">
                <strong>{t("journey.chapter0")}</strong>
                <span className="home-domain-desc">
                  {t("journey.chapter0Help")}
                </span>
                <span className="home-domain-foot">
                  <small>
                    {t("journey.checkpoints", { count: checkpoints })}
                  </small>
                  <span className="home-domain-go">
                    {t("journey.enter")}
                    <ArrowUpRight size={14} aria-hidden="true" />
                  </span>
                </span>
              </span>
            </button>
          </SpotlightCard>
        </Reveal>
        {curriculum?.categories.map((category, index) => {
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
          const tint = categoryTint(category.id);
          const rgb = rgbChannels(tint.color);
          const share = inCategory.length
            ? Math.round((opened / inCategory.length) * 100)
            : 0;
          return (
            <Reveal
              key={category.id}
              index={index + 1}
              data-testid="home-journey-category"
              style={
                { "--tint": tint.color, "--tint-rgb": rgb } as CSSProperties
              }
            >
              <SpotlightCard
                className={`home-domain ${target ? "" : "is-planned"}`}
                spotlightColor={
                  `rgba(${rgbChannels(tint.color, ", ")}, 0.2)` as `rgba(${number}, ${number}, ${number}, ${number})`
                }
              >
                <button
                  type="button"
                  className="home-domain-button"
                  disabled={!target}
                  onClick={() => (target ? onOpenLesson(target.id) : undefined)}
                >
                  <span
                    className="home-domain-sky"
                    aria-hidden="true"
                    style={{ background: tint.sky }}
                  >
                    <span className="home-domain-letter">{category.id}</span>
                    <span className="home-domain-modules">
                      {t("journey.modules", { count: category.modules.length })}
                    </span>
                  </span>
                  <span className="home-domain-body">
                    <strong>{category.title}</strong>
                    <span className="home-domain-desc">
                      {category.description}
                    </span>
                    <span className="home-domain-counts">
                      <small>
                        {t("journey.available", { count: available.length })}
                      </small>
                      <small>
                        {t("journey.planned", {
                          count: inCategory.length - available.length,
                        })}
                      </small>
                    </span>
                    <span className="home-meter" aria-hidden="true">
                      <span style={{ width: `${share}%` }} />
                    </span>
                    <span className="home-domain-foot">
                      <small className="home-progress">
                        {t("journey.meter", {
                          opened,
                          total: inCategory.length,
                        })}
                        {runs > 0 && ` · ${t("journey.runs", { count: runs })}`}
                      </small>
                      <span className="home-domain-go">
                        {target ? t("journey.enter") : t("journey.plannedOnly")}
                        {target && (
                          <ArrowUpRight size={14} aria-hidden="true" />
                        )}
                      </span>
                    </span>
                  </span>
                </button>
              </SpotlightCard>
            </Reveal>
          );
        })}
      </ol>
      <p className="home-honesty">{t("honesty")}</p>
    </section>
  );
}
