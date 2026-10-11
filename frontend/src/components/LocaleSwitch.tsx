import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";
import { changeLocale, locales, type Locale } from "../i18n";
import { isLocale } from "../i18n/locales";
import { useContentLanguage } from "../hooks/useContentLanguage";
import GlideSelect from "./react-bits/GlideSelect";

/**
 * Interface language next to the theme control (same GlideSelect). Each option
 * is written in its own language; the choice is saved by `changeLocale`, and
 * course content refetches in place (see hooks/useContentLanguage).
 */
export function LocaleSwitch() {
  const { t } = useTranslation();
  const language = useContentLanguage();
  return (
    <div
      className="theme-control locale-control"
      title={t("language.control")}
      data-testid="app-locale-switch"
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
