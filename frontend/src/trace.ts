import { TRACE_CONTRACT } from "./generated/trace-contract";
import type { Trace, TraceV2 } from "./types";

export type SpanRule = {
  phase: "start" | "end" | "instant";
  span_kind?: string;
  closed_by?: string;
  opened_by?: string;
  pair_field?: string;
  model_payload?: boolean;
};

const spanEvents: Record<string, SpanRule> = TRACE_CONTRACT.span_events;

/** 与后端 server/envelope.py 的 span_rule 一致：未声明的事件（含 lesson.*）都是瞬时事件。 */
export function spanRuleFor(type: string): SpanRule {
  return Object.hasOwn(spanEvents, type)
    ? spanEvents[type]
    : { phase: "instant" };
}

/** v1 旧记录没有 run_id/seq，只能按数组顺序读取，不能推导 span。 */
export function isTraceV2(event: Trace): event is TraceV2 {
  return (
    event.schema_version === 2 &&
    typeof event.run_id === "string" &&
    typeof event.seq === "number" &&
    typeof event.span_id === "string"
  );
}
