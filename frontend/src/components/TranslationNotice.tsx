import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";
import { translationState, type ContentI18n } from "../i18n/textLanguage";

/**
 * Small note when a lesson or the onboarding is shown (partly) in its Chinese
 * source under another UI language. Nothing in the source language or when
 * the translation is complete.
 */
export function TranslationNotice({ info }: { info?: ContentI18n | null }) {
  const { t } = useTranslation();
  const state = translationState(info);
  if (state !== "none" && state !== "partial") return null;
  return (
    <p
      className="translation-notice"
      role="note"
      data-testid="translation-notice"
      data-state={state}
    >
      <Languages size={14} aria-hidden="true" />
      <span>{t(state === "none" ? "translation.pending" : "translation.partial")}</span>
    </p>
  );
}
