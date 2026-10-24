import { useTranslation } from "react-i18next";
import { ArrowUpRight } from "lucide-react";
import { LINKS } from "../links";
import { Section } from "./Section";

const ITEMS = ["embedding", "injection", "sample"] as const;

/** Known limits, as written in the verification record. */
export function Honesty() {
  const { t } = useTranslation("site", { keyPrefix: "honesty" });
  const links = [
    ["verification", LINKS.verification],
    ["license", LINKS.license],
    ["notices", LINKS.notices],
  ] as const;
  return (
    <Section id="honesty" eyebrow={t("eyebrow")} title={t("title")}>
      <div className="site-honesty">
        <ul data-testid="honesty-limits">
          {ITEMS.map((item) => (
            <li key={item}>{t(item)}</li>
          ))}
        </ul>
        <nav className="site-links" aria-label={t("eyebrow")}>
          {links.map(([key, href]) => (
            <a key={key} href={href}>
              {t(key)}
              <ArrowUpRight size={15} aria-hidden="true" />
            </a>
          ))}
        </nav>
      </div>
    </Section>
  );
}
