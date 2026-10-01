import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LessonHero } from "../components/learning/LessonHero";
import { LessonGuide } from "../components/learning/LessonGuide";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import { Button } from "../components/ui/button";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";

/** 理解：principle first, illustrations clearly labelled, then a way into code and lab. */
export function UnderstandScene({ studio, active, goTo }: SceneProps) {
  const { t } = useTranslation("lesson");
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
            <LessonGuide detail={detail} />
          </LessonExtension>
        </div>
        <aside className="learn-sidebar" aria-label={t("objectives.eyebrow")}>
          <section className="learn-objectives">
            <span className="reading-eyebrow">{t("objectives.eyebrow")}</span>
            <h2>{t("objectives.title")}</h2>
            <ul>
              {detail.objectives.map((objective, index) => (
                <li key={index}>{objective}</li>
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
