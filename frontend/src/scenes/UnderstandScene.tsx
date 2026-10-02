import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { revealProps, useReducedMotion } from "../motion";
import { LessonHero } from "../components/learning/LessonHero";
import { UnderstandBlocks } from "../content/blocks/UnderstandBlocks";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import { Button } from "../components/ui/button";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";

/** 理解：principle first, illustrations clearly labelled, then a way into code and lab. */
export function UnderstandScene({ studio, active, goTo }: SceneProps) {
  const { t } = useTranslation("lesson");
  const reduced = useReducedMotion();
  const detail = studio.detail!;
  return (
    <div
      className="scene-understand learning-experience"
      data-testid="scene-understand"
    >
      <LessonHero
        key={detail.id}
        detail={detail}
        onSource={() => goTo("code")}
      />
      <div className="learn-layout">
        <div className="learn-main" data-testid="learn-main">
          <LessonExtension
            slot="guide"
            extensionKey={detail.ui?.guide}
            studio={studio}
            active={active}
            onStartLab={() => goTo("lab")}
          >
            <UnderstandBlocks
              detail={detail}
              events={studio.events}
              onRun={() => goTo("lab")}
            />
          </LessonExtension>
        </div>
        <aside className="learn-sidebar" aria-label={t("objectives.eyebrow")}>
          <section className="learn-objectives scene-objectives">
            <span className="reading-eyebrow">{t("objectives.eyebrow")}</span>
            <h2>{t("objectives.title")}</h2>
            <ul>
              {detail.objectives.map((objective, index) => (
                <motion.li
                  key={`${detail.id}-${index}`}
                  {...revealProps(
                    reduced,
                    { opacity: 0, x: 18, scale: 0.96, filter: "blur(6px)" },
                    { opacity: 1, x: 0, scale: 1, filter: "blur(0px)" },
                    {
                      delay: 0.15 + index * 0.09,
                      duration: 0.5,
                      ease: [0.16, 1, 0.3, 1],
                    },
                  )}
                  viewport={{ once: true, amount: 0.6 }}
                >
                  {objective}
                </motion.li>
              ))}
            </ul>
          </section>
          <nav className="scene-next" aria-label={t("scenes.region")}>
            <Button variant="outline" onClick={() => goTo("code")}>
              {t("next.code")}
              <ArrowRight size={15} />
            </Button>
            <Button
              data-testid="understand-start-lab"
              onClick={() => goTo("lab")}
            >
              {t("next.lab")}
              <ArrowRight size={15} />
            </Button>
          </nav>
        </aside>
      </div>
    </div>
  );
}
