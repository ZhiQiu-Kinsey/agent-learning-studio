import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Trace } from "../types";
import type { StageSpan } from "./derive";
import { toolSpanStatus, toolSpans } from "./spans";

export const PREVIEW_CHARS = 2000;

function pretty(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

/** Arguments arrive as a JSON string from the model; show parsed JSON or the raw text, never a guess. */
export function parseArguments(raw: unknown): {
  parsed: boolean;
  text: string;
} {
  if (typeof raw !== "string") return { parsed: true, text: pretty(raw ?? {}) };
  try {
    return { parsed: true, text: JSON.stringify(JSON.parse(raw), null, 2) };
  } catch {
    return { parsed: false, text: raw };
  }
}

/** One-line summary built only from what the events contain. */
export function summarize(call: Trace, result: Trace | undefined, limit = 60) {
  const fn = call.data.function as
    { name?: string; arguments?: unknown } | undefined;
  const name = fn?.name ?? String(call.data.name ?? "tool");
  const args = parseArguments(fn?.arguments);
  const compact = (text: string) => {
    const flat = text.replace(/\s+/g, " ");
    return flat.length > limit ? `${flat.slice(0, limit - 1)}…` : flat;
  };
  const value = result?.data.result as
    { ok?: unknown; result?: unknown; error?: unknown } | undefined;
  const outcome =
    value === undefined
      ? null
      : compact(
          pretty(
            value && typeof value === "object" && "result" in value
              ? value.result
              : value,
          ),
        );
  return { name, args: compact(args.text), outcome };
}

function Truncated({ text }: { text: string }) {
  const { t } = useTranslation("stage", { keyPrefix: "tool" });
  const [all, setAll] = useState(false);
  const cut = !all && text.length > PREVIEW_CHARS;
  return (
    <>
      <pre>{cut ? text.slice(0, PREVIEW_CHARS) : text}</pre>
      {cut && (
        <p className="tool-truncated">
          {t("truncated", { total: text.length, shown: PREVIEW_CHARS })}{" "}
          <button type="button" onClick={() => setAll(true)}>
            {t("showAll")}
          </button>
        </p>
      )}
    </>
  );
}

function ToolCard({
  span,
  events,
  defaultOpen,
  onSelect,
}: {
  span: StageSpan;
  events: readonly Trace[];
  defaultOpen: boolean;
  onSelect?: (eventIndex: number) => void;
}) {
  const { t, i18n } = useTranslation("stage", { keyPrefix: "tool" });
  const call = events[span.startIndex];
  const result = span.endIndex != null ? events[span.endIndex] : undefined;
  const summary = summarize(call, result);
  const args = parseArguments(
    (call.data.function as { arguments?: unknown } | undefined)?.arguments,
  );
  const status = toolSpanStatus(span);
  return (
    <details
      className="tool-card"
      data-status={status}
      data-testid="tool-card"
      open={defaultOpen || undefined}
    >
      <summary>
        <code className="tool-name">{summary.name}</code>
        <span className="tool-args">({summary.args})</span>
        {summary.outcome !== null && (
          <span className="tool-outcome">→ {summary.outcome}</span>
        )}
        <span className="tool-status">{t(status)}</span>
        {span.durationMs !== null && (
          <span className="tool-duration">
            {t("duration", {
              value: new Intl.NumberFormat(i18n.language).format(
                span.durationMs,
              ),
            })}
          </span>
        )}
      </summary>
      <div className="tool-body">
        {onSelect && (
          <button
            type="button"
            className="tool-inspect"
            data-testid="tool-card-inspect"
            onClick={() => onSelect(span.endIndex ?? span.startIndex)}
          >
            {t("inspect")}
          </button>
        )}
        <h4>{t("arguments")}</h4>
        {!args.parsed && <p className="tool-truncated">{t("unparsable")}</p>}
        <Truncated text={args.text} />
        <h4>{t("result")}</h4>
        {result ? (
          <Truncated text={pretty(result.data.result)} />
        ) : (
          <p>{t(span.status === "stopped" ? "stopped" : "noResult")}</p>
        )}
      </div>
    </details>
  );
}

/**
 * Tool calls of a run. Groups loaded for replay start collapsed; while a run is
 * live the newest card opens so the learner sees the result arrive.
 */
export function ToolCards({
  spans,
  events,
  live,
  onSelect,
}: {
  spans: StageSpan[];
  events: readonly Trace[];
  live: boolean;
  onSelect?: (eventIndex: number) => void;
}) {
  const { t } = useTranslation("stage", { keyPrefix: "tool" });
  const tools = toolSpans(spans);
  if (!tools.length) return null;
  return (
    <section
      className="tool-cards"
      aria-label={t("region")}
      data-testid="tool-cards"
    >
      <h3>{t("group", { count: tools.length })}</h3>
      {tools.map((span, index) => (
        <ToolCard
          key={`${span.id}-${span.startIndex}`}
          span={span}
          events={events}
          defaultOpen={live && index === tools.length - 1}
          onSelect={onSelect}
        />
      ))}
    </section>
  );
}
