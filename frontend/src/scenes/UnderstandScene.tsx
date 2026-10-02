import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { UnderstandBlocks } from "../content/blocks/UnderstandBlocks";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import { Button } from "../components/ui/button";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";

/**
 * 理解：principle first, illustrations clearly labelled, then a way into code
 * and lab. Title, description and objectives live in the masthead above.
 */
export function UnderstandScene({ studio, active, goTo }: SceneProps) {
  const { t } = useTranslation("lesson");
  const detail = studio.detail!;
  return (
    <div
      className="scene-understand learning-experience"
      data-testid="scene-understand"
    >
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
        <div className="learn-sidebar">
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
        </div>
      </div>
    </div>
  );
}
