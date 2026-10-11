import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { Clock3, ListChecks } from "lucide-react";
import { useReducedMotion } from "../../motion";
import EchoText from "../react-bits/EchoText";
import Shuffle from "../react-bits/Shuffle";
import { Backdrop } from "../backdrops/Backdrop";
import { useResolvedTheme } from "../../hooks/useTheme";
import type { BackdropName } from "../backdrops/presets";
import { numeral, type ChapterContent } from "./chapters";
import { easeOut } from "./transitions";

/** Chapter masthead painted with the chapter's own sky. */
export function ChapterBand({
  chapter,
  index,
  total,
  sky,
}: {
  chapter: ChapterContent;
  index: number;
  total: number;
  sky: BackdropName;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const reduced = useReducedMotion();
  const dark = useResolvedTheme() === "dark";
  return (
    <header className="onboarding-chapter-band">
      <Backdrop name={sky} className="onboarding-band-backdrop" />
      <div className="onboarding-band-scrim" aria-hidden="true" />
      <span className="onboarding-band-numeral" aria-hidden="true">
        {numeral(index)}
      </span>
      <div className="onboarding-band-copy">
        <div className="onboarding-band-top">
          <span className="onboarding-eyebrow">
            <span className="onboarding-band-dot" aria-hidden="true" />
            <Shuffle key={chapter.id} text={chapter.eyebrow} />
          </span>
          <motion.div
            className="onboarding-band-chips"
            initial={reduced ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.45, ease: easeOut }}
          >
            <span>{t("chapterIndex", { index: index + 1, total })}</span>
            <span>
              <Clock3 size={13} aria-hidden="true" />
              {t("minutes", { count: chapter.estimated_minutes })}
            </span>
            <span>
              <ListChecks size={13} aria-hidden="true" />
              {t("sections", { count: chapter.sections.length })}
            </span>
          </motion.div>
        </div>
        <div className="onboarding-band-heading">
          <h2>
            <EchoText
              key={chapter.id}
              text={chapter.title}
              tint={dark ? "#b98aff" : "#7c6cf5"}
              offset={20}
              echoes={7}
            />
          </h2>
          <motion.p
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.35, ease: easeOut }}
          >
            {chapter.summary}
          </motion.p>
        </div>
      </div>
    </header>
  );
}
