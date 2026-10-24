import type { StageSpan } from "./derive";

/** Read-only views over derived spans, shared by the stage, cards and lab chips. */

/** Tool-call spans in run order. */
export const toolSpans = (spans: readonly StageSpan[]) =>
  spans.filter((span) => span.kind === "tool");

/** The model request still waiting for its response, if any. */
export const openLlmSpan = (spans: readonly StageSpan[]) =>
  spans.find((span) => span.kind === "llm" && span.status === "open");

/** The approval gate the run is paused at, if any. */
export const openApprovalSpan = (spans: readonly StageSpan[]) =>
  spans.find((span) => span.kind === "approval" && span.status === "open");

export type ToolSpanStatus =
  "stopped" | "running" | "ok" | "failed" | "undeclared";

/** A tool call's outcome exactly as its events report it; never guessed. */
export function toolSpanStatus(span: StageSpan): ToolSpanStatus {
  return span.status === "stopped"
    ? "stopped"
    : span.status === "open"
      ? "running"
      : span.ok === true
        ? "ok"
        : span.ok === false
          ? "failed"
          : "undeclared";
}
