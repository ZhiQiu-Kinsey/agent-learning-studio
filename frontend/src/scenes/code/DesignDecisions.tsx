import { useTranslation } from "react-i18next";
import FadeContent from "../../components/react-bits/FadeContent";
import GlareHover from "../../components/react-bits/GlareSheen";
import type { Decision } from "../../content/types.gen";

/** 设计决策: what this lesson chose, and why the alternatives were not. */
export function DesignDecisions({ decisions }: { decisions: Decision[] }) {
  const { t } = useTranslation("lesson", { keyPrefix: "code.decisions" });
  if (!decisions.length) return null;
  return (
    <section className="code-decisions" data-testid="code-decisions">
      <span className="reading-eyebrow">{t("eyebrow")}</span>
      <h2>{t("title")}</h2>
      {decisions.map((decision, index) => (
        <FadeContent
          key={decision.id}
          className="code-decision-reveal"
          delay={index * 0.08}
        >
          <GlareHover glareColor="185 138 255" glareOpacity={0.18}>
            <article className="code-decision" data-testid="code-decision">
              <h3>{decision.title}</h3>
              <div className="code-decision-chosen">
                <h4>{t("chosen")}</h4>
                <p>{decision.chosen}</p>
              </div>
              {decision.alternatives.length > 0 && (
                <div className="code-decision-alternatives">
                  <h4>{t("alternatives")}</h4>
                  <ul>
                    {decision.alternatives.map((alternative) => (
                      <li key={alternative.id}>
                        <strong>{alternative.title}</strong>
                        <p>{alternative.why_not}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          </GlareHover>
        </FadeContent>
      ))}
    </section>
  );
}
