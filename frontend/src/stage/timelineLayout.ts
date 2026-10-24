import type { Trace } from "../types";
import type { StageSpan } from "./derive";

export type TimelineScale = "uniform" | "time";

export interface Lane {
  id: string;
  kind: "llm" | "tool" | "approval";
  name?: string;
  bars: { span: StageSpan; left: number; width: number }[];
}

/**
 * Lays spans out in percent. "time" uses server timestamps only; if any are
 * unreadable the whole timeline falls back to uniform spacing (and says so).
 */
export function layoutTimeline(
  events: readonly Trace[],
  spans: StageSpan[],
  scale: TimelineScale,
) {
  const times = events.map((event) => Date.parse(event.timestamp));
  const readable = times.length > 1 && times.every(Number.isFinite);
  const useTime = scale === "time" && readable && times.at(-1)! > times[0];
  const t0 = times[0];
  const total = useTime ? times.at(-1)! - t0 : Math.max(events.length - 1, 1);
  const position = (index: number) =>
    ((useTime ? times[index] - t0 : index) / total) * 100;
  const lanes = new Map<string, Lane>();
  for (const span of spans) {
    const id = span.kind === "tool" ? `tool:${span.name}` : span.kind;
    if (!lanes.has(id))
      lanes.set(id, { id, kind: span.kind, name: span.name, bars: [] });
    const left = position(span.startIndex);
    const end = span.endIndex ?? events.length - 1;
    lanes
      .get(id)!
      .bars.push({ span, left, width: Math.max(position(end) - left, 0.6) });
  }
  return {
    lanes: [...lanes.values()],
    ticks: events.map((_, index) => position(index)),
    totalMs: useTime ? total : null,
    fellBack: scale === "time" && !useTime,
  };
}
