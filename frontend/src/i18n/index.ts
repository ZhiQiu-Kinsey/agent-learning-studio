import i18n from "i18next";
import resourcesToBackend from "i18next-resources-to-backend";
import { initReactI18next } from "react-i18next";
import {
  fallbackLng,
  locales,
  localeStorageKey,
  namespaces,
  pickLocale,
  sourceLocale,
  type Locale,
} from "./locales";
import { sourceResources } from "./resources";

export { locales, sourceLocale, type Locale } from "./locales";

// Other locales load on demand; the source locale (zh-CN) ships with the bundle,
// so it is excluded here (glob patterns must be literals).
const loaders = import.meta.glob<{ default: Record<string, unknown> }>([
  "./locales/*/*.json",
  "!./locales/zh-CN/*.json",
]);

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
  document.title = i18n.t("common:shell.documentTitle", { lng: code });
}

i18n.on("languageChanged", syncDocument);

void i18n
  .use(
    resourcesToBackend((language: string, namespace: string) => {
      const load = loaders[`./locales/${language}/${namespace}.json`];
      return load
        ? load()
        : Promise.reject(new Error(`missing locale ${language}/${namespace}`));
    }),
  )
  .use(initReactI18next)
  .init({
    lng: pickLocale(savedLocale(), navigator.languages ?? []),
    supportedLngs: Object.keys(locales),
    fallbackLng,
    ns: [...namespaces],
    defaultNS: "common",
    resources: { [sourceLocale]: sourceResources },
    partialBundledLanguages: true,
    interpolation: { escapeValue: false }, // React escapes output.
    returnNull: false,
  });

export async function changeLocale(code: Locale) {
  await i18n.changeLanguage(code);
  try {
    localStorage.setItem(localeStorageKey, code);
  } catch {
    /* Keep the session choice. */
  }
}

export default i18n;
