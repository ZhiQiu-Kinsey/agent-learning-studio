import { useTranslation } from "react-i18next";
import FadeContent from "@studio/components/react-bits/FadeContent";
import SpotlightCard from "@studio/components/react-bits/SpotlightCard";
import curriculum from "../generated/curriculum.json";
import type { Curriculum } from "../data/types";
import { asset } from "../links";
import { Section } from "./Section";
import { Text } from "./Text";
import { useSiteLocale } from "./useSiteLocale";

const SHOTS = [
  { id: "request", file: "lesson-lab", wide: true },
  { id: "code", file: "lesson-code", wide: false },
  { id: "lab", file: "lesson-understand", wide: false },
] as const;

/** A bento of what the platform shows, with crops of real screenshots. */
export function Features() {
  const { t } = useTranslation("site", { keyPrefix: "features" });
  const locale = useSiteLocale();
  const { categories } = curriculum as Curriculum;
  return (
    <Section id="features" eyebrow={t("eyebrow")} title={t("title")}>
      <div className="site-bento">
        {SHOTS.map((shot, index) => (
          <FadeContent
            key={shot.id}
            className={`site-bento-cell${shot.wide ? " is-wide" : ""}`}
            delay={index * 0.08}
          >
            <SpotlightCard className="site-bento-card" spotlightColor="rgba(169, 155, 255, 0.18)">
              <div className="site-bento-text">
                <h3>{t(`${shot.id}.title`)}</h3>
                <p>{t(`${shot.id}.body`)}</p>
              </div>
              <div className="site-bento-shot" data-shot={shot.id}>
                <img
                  src={asset(`screenshots/${locale}/${shot.file}.png`)}
                  alt=""
                  loading="lazy"
                  width={1440}
                  height={900}
                />
              </div>
            </SpotlightCard>
          </FadeContent>
        ))}
        <FadeContent className="site-bento-cell is-wide is-route" delay={0.24}>
          <SpotlightCard className="site-bento-card" spotlightColor="rgba(73, 222, 198, 0.16)">
            <div className="site-bento-text">
              <h3>{t("route.title")}</h3>
              <p>{t("route.body")}</p>
            </div>
            <ol className="site-route" aria-label={t("route.title")}>
              {categories.map((category) => (
                <li key={category.id}>
                  <b>{category.id}</b>
                  <Text value={category.title} />
                </li>
              ))}
            </ol>
          </SpotlightCard>
        </FadeContent>
      </div>
    </Section>
  );
}
