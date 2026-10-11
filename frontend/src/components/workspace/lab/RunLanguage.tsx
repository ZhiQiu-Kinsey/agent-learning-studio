import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";
import type { Trace } from "../../../types";

/** Two tags name the same language: "en" and "en-US", "zh" and "zh-CN". */
export function sameLanguage(a: string, b: string) {
  return a.split("-")[0].toLowerCase() === b.split("-")[0].toLowerCase();
}

/**
 * The language a run was recorded in (`run_start.data.locale`). Runs recorded
 * before the field existed always ran in Chinese. No run_start: no run yet.
 */
export function runLocaleOf(events: readonly Trace[]): string | null {
  const start = events.find((event) => event.type === "run_start");
  if (!start) return null;
  return typeof start.data.locale === "string" ? start.data.locale : "zh-CN";
}

/**
 * Names the language of a run (`kind="run"`) or of a lesson's runner
 * (`kind="runtime"`) when it differs from the UI language. Run data is never
 * translated, so an English UI can show a Chinese run; this says so.
 */
export function RuntimeLanguageNote({
  locale,
  kind,
  testId,
}: {
  locale: string | null | undefined;
  kind: "run" | "runtime";
  testId: string;
}) {
  const { t, i18n } = useTranslation("lab");
  if (!locale || sameLanguage(locale, i18n.language)) return null;
  const language = t(`language.${locale}` as "language.en", {
    defaultValue: locale,
  });
  return (
    <p
      className="composer-note run-language-note"
      role="note"
      data-testid={testId}
      data-locale={locale}
    >
      <Languages size={14} aria-hidden="true" />
      <span>
        {kind === "run"
          ? t("bench.answer.runLocale", { language })
          : t("bench.composer.runtimeLocale", { language })}
      </span>
    </p>
  );
}
