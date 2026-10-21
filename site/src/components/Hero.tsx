import { ArrowRight, PlayCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import FadeContent from "@studio/components/react-bits/FadeContent";
import GradientText from "@studio/components/react-bits/GradientText";
import StarBorder from "@studio/components/react-bits/StarBorder";
import { useResolvedTheme } from "@studio/hooks/useTheme";
import { asset } from "../links";
import { HeroBackdrop } from "./HeroBackdrop";
import { useSiteLocale } from "./useSiteLocale";

// Light theme uses the platform's role colours, which stay readable on the pale band.
const ACCENT = {
  dark: ["#a99bff", "#49dec6", "#ff9473", "#a99bff"],
  light: ["#5a45cf", "#226389", "#0a7069", "#5a45cf"],
} as const;

export function Hero() {
  const { t } = useTranslation("site", { keyPrefix: "hero" });
  const theme = useResolvedTheme();
  const locale = useSiteLocale();
  return (
    <section className="site-hero" id="top" aria-labelledby="hero-title">
      <HeroBackdrop />
      <div className="site-hero-inner">
        <FadeContent className="site-hero-copy">
          <p className="site-eyebrow">{t("eyebrow")}</p>
          <h1 id="hero-title">
            <span>{t("titleLead")}</span>
            <GradientText
              className="site-hero-accent"
              colors={[...ACCENT[theme]]}
            >
              {t("titleAccent")}
            </GradientText>
          </h1>
          <p className="site-lead">{t("lead")}</p>
          <div className="site-cta">
            <StarBorder className="site-star" color="#49dec6">
              <a className="site-button is-primary" href="#replays">
                <PlayCircle size={18} aria-hidden="true" />
                {t("ctaReplay")}
              </a>
            </StarBorder>
            <a className="site-button is-ghost" href="#start">
              {t("ctaStart")}
              <ArrowRight size={17} aria-hidden="true" />
            </a>
          </div>
        </FadeContent>
        <FadeContent className="site-hero-shot" delay={0.15} distance={40}>
          <div className="site-window">
            <div className="site-window-bar" aria-hidden="true">
              <i />
              <i />
              <i />
              <span>127.0.0.1:8765</span>
            </div>
            <img
              src={asset(`screenshots/${locale}/home.png`)}
              alt={t("shotAlt")}
              width={1440}
              height={900}
            />
          </div>
        </FadeContent>
      </div>
    </section>
  );
}
