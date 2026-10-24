import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";
import { isLocale } from "@studio/i18n/locales";
import GlideSelect from "@studio/components/react-bits/GlideSelect";
import { changeLocale, locales, type Locale } from "../i18n";
import { useSiteLocale } from "./useSiteLocale";

/** Same control as the platform's language switch; each option is written in its own language. */
export function LocaleSwitch() {
  const { t } = useTranslation("site");
  const language = useSiteLocale();
  return (
    <div
      className="theme-control locale-control"
      title={t("language.control")}
      data-testid="site-locale-switch"
    >
      <Languages size={16} aria-hidden="true" className="locale-control-icon" />
      <GlideSelect
        ariaLabel={t("language.label")}
        value={language}
        options={(Object.keys(locales) as Locale[]).map((code) => ({
          value: code,
          label: <span lang={code}>{locales[code].label}</span>,
        }))}
        size="sm"
        align="right"
        menuWidth={136}
        accentColor="var(--text)"
        surfaceColor="var(--surface)"
        highlightColor="var(--surface-muted)"
        textColor="var(--text)"
        onChange={(value) => {
          if (isLocale(value)) void changeLocale(value);
        }}
      />
    </div>
  );
}
