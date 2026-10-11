import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { jsonFetch } from "../../api";
import { useContentLanguage } from "../../hooks/useContentLanguage";
import type { Onboarding } from "../../content/types.gen";
import type { ContentI18n } from "../../i18n/textLanguage";

/** Onboarding as served: plus which language its text is actually in. */
export type LocalizedOnboarding = Onboarding & { i18n?: ContentI18n };

/** Loads `/api/onboarding`; `retry` starts a fresh request after a failure. */
export function useOnboardingContent() {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const [content, setContent] = useState<LocalizedOnboarding | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const language = useContentLanguage();
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    jsonFetch<LocalizedOnboarding>(
      "/api/onboarding",
      { signal: controller.signal },
      language,
    )
      .then(setContent)
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : t("readFailed"));
      });
    return () => controller.abort();
  }, [attempt, language, t]);
  const retry = () => setAttempt((value) => value + 1);
  return { content, error, retry };
}
