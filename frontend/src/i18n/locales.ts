/**
 * Locale registry. Adding a language = adding an entry here plus
 * `locales/<code>/*.json` with the same keys (checked by scripts/check-i18n-keys.mjs).
 * UI language is independent of lesson content's own source-language tag.
 */
interface LocaleInfo {
  /** Name shown in its own language. */
  label: string;
  dir: "ltr" | "rtl";
}

export const locales = {
  "zh-CN": { label: "简体中文", dir: "ltr" },
} as const satisfies Record<string, LocaleInfo>;

export type Locale = keyof typeof locales;
export const sourceLocale: Locale = "zh-CN";
export const localeStorageKey = "agent-lab-locale";
export const namespaces = [
  "common",
  "settings",
  "quiz",
  "lab",
  "errors",
  "stage",
  "lesson",
  "blocks",
  "home",
  "command",
] as const;
export type Namespace = (typeof namespaces)[number];

/** Object-form fallback chain: every locale ends at the source locale. */
export const fallbackLng = { default: [sourceLocale] };

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && Object.hasOwn(locales, value);
}

export function pickLocale(
  saved: string | null | undefined,
  browser: readonly string[],
): Locale {
  if (isLocale(saved)) return saved;
  for (const tag of browser) {
    if (isLocale(tag)) return tag;
    const base = Object.keys(locales).find(
      (code) => code.split("-")[0] === tag.split("-")[0],
    );
    if (base) return base as Locale;
  }
  return sourceLocale;
}
