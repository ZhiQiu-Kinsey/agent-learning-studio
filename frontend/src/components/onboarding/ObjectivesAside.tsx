import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { ArrowRight, Check, Compass } from "lucide-react";
import { useReducedMotion } from "../../motion";
import { Button } from "../ui/button";
import SpotlightCard from "../react-bits/SpotlightCard";
import type { ChapterContent } from "./chapters";
import { easeOut } from "./transitions";

/** Side column: the chapter's objectives and a pacing note with a way out. */
export function ObjectivesAside({
  chapter,
  onStart,
}: {
  chapter: ChapterContent;
  onStart: () => void;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const reduced = useReducedMotion();
  return (
    <aside className="onboarding-aside">
      <SpotlightCard
        className="onboarding-objectives"
        spotlightColor="rgba(122, 100, 240, 0.15)"
      >
        <Compass size={25} />
        <h3>{t("objectives")}</h3>
        <ul key={chapter.id}>
          {chapter.objectives.map((item, index) => (
            <motion.li
              key={item}
              initial={reduced ? false : { opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{
                duration: 0.45,
                delay: 0.2 + index * 0.08,
                ease: easeOut,
              }}
            >
              <Check size={14} />
              {item}
            </motion.li>
          ))}
        </ul>
      </SpotlightCard>
      <div className="onboarding-aside-note">
        <span>{t("paceTitle")}</span>
        <p>{t("paceBody")}</p>
        <Button variant="link" onClick={onStart}>
          {t("ready")} <ArrowRight size={14} />
        </Button>
      </div>
    </aside>
  );
}
