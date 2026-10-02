import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { useReducedMotion } from "../../motion";
import type { Chapter } from "../../content/types.gen";
import { backdropAccent } from "../curriculum/atmosphere";
import { useResolvedTheme } from "../../hooks/useTheme";
import { chapterChecks, numeral, skyFor, type CheckedPoints } from "./chapters";
import { tabSpring } from "./transitions";

/** Thin ring showing how many checkpoints of a chapter were self-reported. */
function CheckRing({ done, total }: { done: number; total: number }) {
  const ratio = total ? done / total : 0;
  return (
    <svg className="onboarding-tab-ring" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="8" pathLength={1} />
      <circle
        cx="10"
        cy="10"
        r="8"
        pathLength={1}
        strokeDasharray={1}
        style={{ strokeDashoffset: 1 - ratio }}
      />
    </svg>
  );
}

/** Chapter tabs, each tinted with its chapter sky and its checkpoint ring. */
export function ChapterTabs({
  chapters,
  activeIndex,
  checked,
  onNavigate,
}: {
  chapters: Chapter[];
  activeIndex: number;
  checked: CheckedPoints;
  onNavigate: (index: number) => void;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const reduced = useReducedMotion();
  const theme = useResolvedTheme();
  return (
    <nav
      className="onboarding-chapter-tabs"
      aria-label={t("tabsLabel")}
      data-testid="onboarding-chapter-tabs"
    >
      {chapters.map((item, index) => {
        const { done, total } = chapterChecks(item, checked);
        const active = activeIndex === index;
        return (
          <button
            type="button"
            key={item.id}
            className={active ? "is-active" : ""}
            aria-current={active ? "step" : undefined}
            data-complete={total > 0 && done === total}
            style={
              {
                "--tab-rgb": backdropAccent(skyFor(item.id, index), theme),
              } as CSSProperties
            }
            onClick={() => onNavigate(index)}
          >
            {active && (
              <motion.i
                className="onboarding-tab-pill"
                layoutId="onboarding-chapter"
                transition={reduced ? { duration: 0 } : tabSpring}
                aria-hidden="true"
              />
            )}
            <span className="onboarding-tab-number">{numeral(index)}</span>
            <strong>{item.title}</strong>
            <small>{t("minutes", { n: item.estimated_minutes })}</small>
            {/* Self-check progress, not a selection mark: say so with the count. */}
            <span className="onboarding-tab-checks">
              <span className="onboarding-tab-count" aria-hidden="true">
                {done}/{total}
              </span>
              <CheckRing done={done} total={total} />
              <span className="sr-only">{t("tabChecks", { done, total })}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
