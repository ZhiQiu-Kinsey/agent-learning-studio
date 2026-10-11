import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { sourceLocale } from "../i18n/locales";
import { fallbackLang } from "../i18n/textLanguage";

/**
 * The language course content is requested in (the UI language). Effects that
 * fetch localized endpoints list it as a dependency, so switching language
 * refetches them in place without reloading the page.
 */
export function useContentLanguage() {
  const { i18n } = useTranslation();
  return i18n.resolvedLanguage ?? i18n.language ?? sourceLocale;
}

/** `lang` attribute for a course string that fell back to Chinese under another UI language. */
export function useFallbackLang() {
  const language = useContentLanguage();
  return useCallback(
    (text: string | null | undefined) => fallbackLang(text, language),
    [language],
  );
}
