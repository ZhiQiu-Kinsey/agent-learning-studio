import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { jsonFetch } from "../../api";
import type { Onboarding } from "../../content/types.gen";

/** Loads `/api/onboarding`; `retry` starts a fresh request after a failure. */
export function useOnboardingContent() {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const [content, setContent] = useState<Onboarding | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    jsonFetch<Onboarding>("/api/onboarding", {
      signal: controller.signal,
    })
      .then(setContent)
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : t("readFailed"));
      });
    return () => controller.abort();
  }, [attempt, t]);
  const retry = () => setAttempt((value) => value + 1);
  return { content, error, retry };
}
