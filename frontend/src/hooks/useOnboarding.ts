import { useEffect, useState } from "react";
import { jsonFetch } from "../api";
import type { Onboarding } from "../content/types.gen";
import { createLanguageCache } from "../lib/languageCache";
import { useContentLanguage } from "./useContentLanguage";

// One request per language, shared by the home page, sidebar and command palette.
const onboardings = createLanguageCache((language) =>
  jsonFetch<Onboarding>("/api/onboarding", undefined, language),
);

/**
 * Shared, cached onboarding content in the UI language; null until loaded or
 * when unavailable (callers then show nothing or their own fallback). The
 * previous language's content stays until the new one arrives.
 */
export function useOnboarding() {
  const language = useContentLanguage();
  const [data, setData] = useState<Onboarding | null>(
    () => onboardings.peek(language) ?? null,
  );
  useEffect(() => {
    let alive = true;
    onboardings
      .load(language)
      .then((value) => alive && setData(value))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [language]);
  return data;
}
