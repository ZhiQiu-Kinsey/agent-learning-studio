import { useTranslation } from "react-i18next";
import { ArrowRight, Compass, Map as MapIcon } from "lucide-react";
import ParticleText from "../react-bits/ParticleText";
import Shuffle from "../react-bits/Shuffle";

/**
 * Closing band: the course promise as large particle words (decoration; the
 * same words are real text underneath) and the two ways in.
 */
export function HomeOutro({
  onStartOnboarding,
  onOpenMap,
}: {
  onStartOnboarding: () => void;
  onOpenMap: () => void;
}) {
  const { t } = useTranslation("home");
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
        <ParticleText text={t("outro.word")} className="home-outro-particles" />
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
