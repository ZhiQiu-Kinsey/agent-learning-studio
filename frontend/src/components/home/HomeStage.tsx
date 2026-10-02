import { useTranslation } from "react-i18next";
import { Hand } from "lucide-react";
import BorderGlow from "../react-bits/BorderGlow";
import AnimatedContent from "../react-bits/AnimatedContent";
import { IllustrationFlow } from "../../content/blocks/IllustrationFlow";
import type { Flow, Illustration } from "../../content/types.gen";
import Shuffle from "../react-bits/Shuffle";

/**
 * The authored Agent loop on the real stage. It stays an illustration: the
 * stage watermarks it, the frame says so again, and it only moves when the
 * learner steps it or presses play (never on load).
 */
export function HomeStage({
  block,
  illustration,
}: {
  block: Flow;
  illustration: Illustration;
}) {
  const { t } = useTranslation("home");
  return (
    <section
      className="home-section home-stage"
      aria-labelledby="home-stage-title"
    >
      <header className="home-section-head home-stage-head">
        <div>
          <p className="home-eyebrow">
            <Shuffle text={t("stage.kicker")} />
          </p>
          <h2 id="home-stage-title">{t("stageTitle")}</h2>
          <p>{t("stage.lead")}</p>
        </div>
        <div className="home-stage-notes">
          <span className="home-stage-badge">{t("stage.badge")}</span>
          <span className="home-stage-manual">
            <Hand size={14} aria-hidden="true" />
            {t("stage.manual")}
          </span>
        </div>
      </header>
      <AnimatedContent
        distance={60}
        duration={0.9}
        scale={0.97}
        threshold={0.12}
      >
        <BorderGlow
          className="home-stage-frame"
          backgroundColor="var(--surface)"
          borderRadius={22}
          glowRadius={24}
          glowColor="250 90 78"
          glowIntensity={0.9}
          edgeSensitivity={26}
          colors={["#b98aff", "#49dec6", "#6d5dfc"]}
          fillOpacity={0.35}
        >
          <ul className="home-stage-legend">
            <li data-role="model">{t("stage.legendModel")}</li>
            <li data-role="runtime">{t("stage.legendRuntime")}</li>
            <li data-role="tool">{t("stage.legendTool")}</li>
          </ul>
          <IllustrationFlow block={block} illustration={illustration} />
        </BorderGlow>
      </AnimatedContent>
    </section>
  );
}
