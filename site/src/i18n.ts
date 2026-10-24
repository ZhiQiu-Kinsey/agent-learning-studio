import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import {
  locales,
  pickLocale,
  sourceLocale,
  type Locale,
} from "@studio/i18n/locales";
// The replay viewer reuses the platform's components, which read these namespaces.
import zhCommon from "@studio/i18n/locales/zh-CN/common.json";
import zhLab from "@studio/i18n/locales/zh-CN/lab.json";
import zhStage from "@studio/i18n/locales/zh-CN/stage.json";
import zhLesson from "@studio/i18n/locales/zh-CN/lesson.json";
import enCommon from "@studio/i18n/locales/en/common.json";
import enLab from "@studio/i18n/locales/en/lab.json";
import enStage from "@studio/i18n/locales/en/stage.json";
import enLesson from "@studio/i18n/locales/en/lesson.json";
import zhSite from "./locales/zh-CN/site.json";
import enSite from "./locales/en/site.json";

export { locales, type Locale };

/** Separate from the platform's key: the site is another origin anyway, but keep them apart. */
export const localeStorageKey = "als-site-locale";

export const resources = {
  "zh-CN": {
    site: zhSite,
    common: zhCommon,
    lab: zhLab,
    stage: zhStage,
    lesson: zhLesson,
  },
  en: {
    site: enSite,
    common: enCommon,
    lab: enLab,
    stage: enStage,
    lesson: enLesson,
  },
} as const;

function savedLocale() {
  try {
    return localStorage.getItem(localeStorageKey);
  } catch {
    return null;
  }
}

function syncDocument(code: string) {
  const info = locales[code as Locale] ?? locales[sourceLocale];
  document.documentElement.lang = code;
  document.documentElement.dir = info.dir;
  document.title = i18n.t("site:meta.title", { lng: code });
}

i18n.on("languageChanged", syncDocument);

void i18n.use(initReactI18next).init({
  // Saved choice first, then the browser's languages, then the source locale.
  lng: pickLocale(savedLocale(), navigator.languages ?? []),
  supportedLngs: Object.keys(locales),
  fallbackLng: sourceLocale,
  ns: ["site", "common", "lab", "stage", "lesson"],
  defaultNS: "site",
  resources,
  interpolation: { escapeValue: false }, // React escapes output.
  returnNull: false,
});

export async function changeLocale(code: Locale) {
  await i18n.changeLanguage(code);
  try {
    localStorage.setItem(localeStorageKey, code);
  } catch {
    /* Keep the choice for this visit. */
  }
}

export default i18n;
