import { useEffect, useState } from "react";
import { Github } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ThemeSwitch } from "@studio/components/ThemeSwitch";
import { REPO, asset } from "../links";
import { LocaleSwitch } from "./LocaleSwitch";

const SECTIONS = ["curriculum", "replays", "start", "honesty"] as const;

export function Header() {
  const { t } = useTranslation("site");
  // Transparent over the hero, solid once the page has scrolled.
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 24);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);
  return (
    <header className="site-header" data-scrolled={scrolled || undefined}>
      <a className="skip-link" href="#main">
        {t("nav.skip")}
      </a>
      <div className="site-header-row">
        <a className="site-brand" href="#top">
          <img src={asset("favicon.svg")} alt="" width={26} height={26} />
          <span>Agent Learning Studio</span>
        </a>
        <nav className="site-nav" aria-label={t("nav.primary")}>
          {SECTIONS.map((id) => (
            <a key={id} href={`#${id}`}>
              {t(`nav.${id}`)}
            </a>
          ))}
        </nav>
        <div className="site-controls">
          <LocaleSwitch />
          <ThemeSwitch />
          <a className="site-icon-link" href={REPO} aria-label={t("nav.github")} title={t("nav.github")}>
            <Github size={18} aria-hidden="true" />
          </a>
        </div>
      </div>
    </header>
  );
}
