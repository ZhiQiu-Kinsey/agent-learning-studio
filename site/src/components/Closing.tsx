import { ArrowRight, Github } from "lucide-react";
import { useTranslation } from "react-i18next";
import FadeContent from "@studio/components/react-bits/FadeContent";
import { REPO } from "../links";

export function Closing() {
  const { t } = useTranslation("site", { keyPrefix: "cta" });
  return (
    <section className="site-closing" aria-labelledby="closing-title">
      <FadeContent className="site-closing-inner">
        <h2 id="closing-title">{t("title")}</h2>
        <p>{t("lead")}</p>
        <div className="site-cta">
          <a className="site-button is-primary" href={REPO}>
            <Github size={18} aria-hidden="true" />
            {t("github")}
          </a>
          <a className="site-button is-ghost" href="#start">
            {t("start")}
            <ArrowRight size={17} aria-hidden="true" />
          </a>
        </div>
      </FadeContent>
    </section>
  );
}
