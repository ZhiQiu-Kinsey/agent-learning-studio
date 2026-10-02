import { useTranslation } from "react-i18next";
import type { StageSpan } from "../../../stage/derive";
import { toolSpanStatus, toolSpans } from "../../../stage/spans";
import { summarize } from "../../../stage/ToolCards";
import type { Trace } from "../../../types";
import CallChip, { type CallChipStatus } from "../../react-bits/CallChip";

/** Stage tool status → CallChip's own status names. */
const chipStatus = {
  stopped: "stopped",
  running: "running",
  ok: "done",
  failed: "error",
  undeclared: "unknown",
} as const satisfies Record<string, CallChipStatus>;

/** One chip per real tool call at the cursor; times come from server timestamps. */
export function ToolCallChips({
  spans,
  events,
  live,
  activeIndex,
  onSelect,
}: {
  spans: StageSpan[];
  events: readonly Trace[];
  live: boolean;
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "bench.calls" });
  const tools = toolSpans(spans);
  if (!tools.length) return null;
  const number = new Intl.NumberFormat(i18n.language, {
    maximumFractionDigits: 1,
  });
  const formatMs = (ms: number) =>
    ms < 1000
      ? t("ms", { value: number.format(Math.round(ms)) })
      : t("s", { value: number.format(ms / 1000) });
  return (
    <ul
      className="tool-call-chips"
      aria-label={t("region")}
      data-testid="lab-call-chips"
    >
      {tools.map((span) => {
        const call = events[span.startIndex];
        const { name, args } = summarize(call, undefined, 28);
        const status: CallChipStatus = chipStatus[toolSpanStatus(span)];
        // Only a call that is open right now ticks; a replayed open call shows no time.
        const startAt = status === "running" && live ? span.startAt : null;
        const time =
          span.durationMs != null ? formatMs(span.durationMs) : t("noTime");
        const target = span.endIndex ?? span.startIndex;
        return (
          <li key={`${span.id}-${span.startIndex}`}>
            <CallChip
              name={name}
              argument={args}
              status={status}
              startAt={startAt}
              durationMs={status === "running" ? null : span.durationMs}
              formatMs={formatMs}
              statusLabel={
                status === "running"
                  ? t("running", { name })
                  : status === "stopped"
                    ? t("stopped", { name })
                    : t(status === "unknown" ? "undeclared" : status, {
                        name,
                        time,
                      })
              }
              pressed={
                activeIndex >= span.startIndex &&
                activeIndex <= (span.endIndex ?? span.startIndex)
              }
              onClick={() => onSelect(target)}
              data-testid="lab-call-chip"
            />
          </li>
        );
      })}
    </ul>
  );
}
