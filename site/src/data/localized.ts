import type { Localized, SiteLocale } from "./types";

/**
 * The text for the UI language. A missing or stale translation shows the source
 * text, marked with its own language so screen readers and fonts get it right.
 */
export function pick(text: Localized, locale: SiteLocale) {
  const translated = locale === "zh-CN" ? text["zh-CN"] : text[locale];
  return translated
    ? { text: translated, lang: undefined }
    : { text: text["zh-CN"], lang: locale === "zh-CN" ? undefined : "zh-CN" };
}

export const siteLocale = (language: string): SiteLocale =>
  language.startsWith("zh") ? "zh-CN" : "en";
