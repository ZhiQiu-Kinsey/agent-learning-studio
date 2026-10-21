import { useTranslation } from "react-i18next";
import { siteLocale } from "../data/localized";

/** The UI language as one of the site's two locales. */
export function useSiteLocale() {
  const { i18n } = useTranslation();
  return siteLocale(i18n.resolvedLanguage ?? i18n.language);
}
