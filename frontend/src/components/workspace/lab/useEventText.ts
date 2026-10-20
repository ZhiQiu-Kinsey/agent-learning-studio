import { useMemo } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import type { Trace } from "../../../types";
import { embeddingFacts, isEmbeddingEvent } from "./embeddings";

const NAMED = new Set([
  "run_start",
  "request",
  "response",
  "tool_call",
  "tool_result",
  "answer",
  "error",
  "done",
]);

const isSdkExchange = (e: Trace) =>
  e.data.representation === "sdk_standardized" &&
  (e.type === "request" || e.type === "response");

type EventT = TFunction<"lab", "bench.event">;

/**
 * Title and one-line summary of a run event, built only from what the event
 * contains. Lesson-specific events fall back to their own title / summary.
 */
export function useEventText() {
  const { t } = useTranslation("lab", { keyPrefix: "bench.event" });
  return useMemo(() => eventText(t), [t]);
}

/** The texts for one translation function; split out so tests can check them without React. */
export function eventText(t: EventT) {
  function label(e: Trace): string {
    if (e.type === "tool_call" && e.data.origin === "course_program")
      return t("programCall");
    if (isEmbeddingEvent(e))
      return e.type === "request"
        ? t("embeddingRequest")
        : t("embeddingResponse");
    if (isSdkExchange(e))
      return e.type === "request" ? t("sdkRequest") : t("sdkResponse");
    if (NAMED.has(e.type)) return t(`name.${e.type}` as "name.run_start");
    return typeof e.data.title === "string" ? e.data.title : e.type;
  }
  function summary(e: Trace): string {
    if (e.type === "tool_call") {
      const fn = e.data.function as
        { name?: string; arguments?: string } | undefined;
      return fn
        ? `${fn.name}(${fn.arguments || ""})`
        : String(e.data.name || t("toolCall"));
    }
    if (e.type === "tool_result")
      return t(
        (e.data.result as { ok?: boolean })?.ok === false
          ? "toolError"
          : "toolDone",
        { name: String(e.data.name || t("tool")) },
      );
    if (isEmbeddingEvent(e)) {
      const facts = embeddingFacts(e);
      if (e.type === "request")
        return t("embeddingRequestSummary", {
          count: facts.count,
          model: facts.model ?? "?",
          dimensions: facts.dimensions ?? t("embeddingDefaultDimensions"),
        });
      return t("embeddingResponseSummary", {
        count: facts.count,
        dimensions: facts.dimensions ?? t("embeddingUnknownDimensions"),
        seconds:
          typeof e.data.duration_ms === "number"
            ? (e.data.duration_ms / 1000).toFixed(2)
            : "?",
      });
    }
    if (e.type === "request") return t("request", { round: e.round || 1 });
    if (e.type === "response")
      return typeof e.data.duration_ms === "number"
        ? t("seconds", { value: (e.data.duration_ms / 1000).toFixed(2) })
        : t("responded");
    if (e.type === "answer") return String(e.data.content || "");
    if (e.type === "error") return String(e.data.message || t("errorDetail"));
    if (e.type === "done") return String(e.data.status || t("ended"));
    if (e.type === "run_start") return t("runStart");
    return typeof e.data.summary === "string"
      ? e.data.summary
      : typeof e.data.title === "string"
        ? e.data.title
        : t("custom");
  }
  return { label, summary };
}
