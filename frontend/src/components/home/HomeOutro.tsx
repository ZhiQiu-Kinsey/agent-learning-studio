import { useTranslation } from "react-i18next";
import { ArrowRight, Compass, Map as MapIcon } from "lucide-react";
import GradientText from "../react-bits/GradientText";
import Shuffle from "../react-bits/Shuffle";
import { useResolvedTheme } from "../../hooks/useTheme";

/** Gradient stops per theme: brand pastels on ink, deeper brand tones on paper. */
const gradients = {
  dark: ["#e6ddff", "#b98aff", "#7fe6d4", "#b98aff"],
  light: ["#3b2db0", "#6d5dfc", "#0f9e8a", "#6d5dfc"],
};

/**
 * Closing band: the course promise as large, crisp words with a slowly
 * flowing gradient and a soft halo, then the two ways in.
 */
export function HomeOutro({
  onStartOnboarding,
  onOpenMap,
}: {
  onStartOnboarding: () => void;
  onOpenMap: () => void;
}) {
  const { t } = useTranslation("home");
  const theme = useResolvedTheme();
  return (
    <section
      className="home-section home-outro"
      aria-labelledby="home-outro-title"
      data-testid="home-outro"
    >
      <div className="home-outro-glow" aria-hidden="true" />
      <p className="home-eyebrow home-outro-kicker">
        <Shuffle text={t("outro.kicker")} />
      </p>
      <h2 id="home-outro-title" className="home-outro-title">
        <span className="home-outro-word">
          <GradientText colors={gradients[theme]} animationSpeed={9}>
            {t("outro.word")}
          </GradientText>
        </span>
      </h2>
      <p className="home-outro-lead">{t("outro.lead")}</p>
      <div className="home-outro-actions">
        <button
          type="button"
          className="home-cta home-cta-primary"
          onClick={onStartOnboarding}
        >
          <Compass size={17} aria-hidden="true" />
          {t("startOnboarding")}
          <ArrowRight size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="home-cta home-cta-glass"
          onClick={onOpenMap}
        >
          <MapIcon size={17} aria-hidden="true" />
          {t("map")}
        </button>
      </div>
    </section>
  );
}
