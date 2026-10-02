import { ArrowUp, Code2, FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";
import { prefersReducedMotionNow } from "../motion";
import { UnderstandBlocks } from "../content/blocks/UnderstandBlocks";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import Dock from "../components/react-bits/Dock";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";

/**
 * 理解：principle first, illustrations clearly labelled, then a way into code
 * and lab. Title, description and objectives live in the masthead above; the
 * ways on float in a dock so the reading column keeps the full width.
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
      </div>
      <Dock
        className="scene-dock"
        label={t("next.dock")}
        items={[
          {
            icon: <ArrowUp size={18} />,
            label: t("next.top"),
            onClick: () =>
              window.scrollTo({
                top: 0,
                behavior: prefersReducedMotionNow() ? "instant" : "smooth",
              }),
          },
          {
            icon: <Code2 size={18} />,
            label: t("next.code"),
            onClick: () => goTo("code"),
          },
          {
            icon: <FlaskConical size={18} />,
            label: t("next.lab"),
            onClick: () => goTo("lab"),
            className: "is-primary",
            testId: "understand-start-lab",
          },
        ]}
      />
    </div>
  );
}
