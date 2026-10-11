/**
 * Mixed-language honesty. Course text falls back to the Chinese source string
 * by string when a translation is missing or stale, so under a non-Chinese UI
 * a Chinese string is marked `lang="zh-CN"` (screen readers, fonts). A string
 * counts as Chinese when Han characters carry most of it: one Han character
 * is weighed like a short word, so an English sentence that quotes a Chinese
 * phrase stays English.
 */

const HAN = /\p{Script=Han}/gu;
const LATIN = /[A-Za-z]/g;

export function isChineseText(text: string) {
  const han = text.match(HAN)?.length ?? 0;
  if (!han) return false;
  const latin = text.match(LATIN)?.length ?? 0;
  return han * 3 >= latin;
}

/** `lang` for a course string shown in `uiLanguage`; undefined when it matches the page. */
export function fallbackLang(
  text: string | null | undefined,
  uiLanguage: string,
): "zh-CN" | undefined {
  if (!text || uiLanguage.toLowerCase().startsWith("zh")) return undefined;
  return isChineseText(text) ? "zh-CN" : undefined;
}

/** What the server reports about one localized document (`learning_i18n`, `i18n`). */
export interface ContentI18n {
  requested: string;
  locale: string;
  source_language: string;
  total: number;
  translated: number;
  missing: string[];
  stale: string[];
  error?: string;
}

export type TranslationState = "source" | "complete" | "partial" | "none";

/**
 * source: the UI asked for the source language; none: nothing translated
 * (no overlay, or a broken one); partial: some strings fell back.
 */
export function translationState(info: ContentI18n | null | undefined): TranslationState {
  if (!info || info.requested === info.source_language) return "source";
  if (info.locale === info.source_language || !info.translated) return "none";
  return info.missing.length || info.stale.length ? "partial" : "complete";
}
