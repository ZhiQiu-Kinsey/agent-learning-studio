import { useTranslation } from "react-i18next";
import FadeContent from "@studio/components/react-bits/FadeContent";
import { Section } from "./Section";

const STEPS = ["concept", "implementation", "evidence", "experiment", "check"] as const;

export function Loop() {
  const { t } = useTranslation("site", { keyPrefix: "loop" });
  return (
    <Section id="method" eyebrow={t("eyebrow")} title={t("title")}>
      <ol className="site-loop" data-testid="loop">
        {STEPS.map((step, index) => (
          <FadeContent as="li" key={step} delay={index * 0.08}>
            <span className="site-loop-index" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
            </span>
            <h3>{t(`${step}.title`)}</h3>
            <p>{t(`${step}.body`)}</p>
          </FadeContent>
        ))}
      </ol>
    </Section>
  );
}
