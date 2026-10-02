import type { Trace } from "../types";
import { matches, selectEvents } from "./selector";
import type { Selector } from "./types.gen";

/**
 * 轨迹找错（trace-hunt）：在学习者自己这次真实运行的事件里，找出满足课程声明
 * 选择器的那一步。判定只用选择器引擎，不读示意或录制，也不替学习者造证据。
 */

export const selectorConditions = [
  "event",
  "round",
  "span_kind",
  "name",
  "path",
] as const;
export type SelectorCondition = (typeof selectorConditions)[number];

/** 只算本机真实运行产生的事件；随课录制与教学示意都不能充当学习者的证据。 */
export function ownRunEvents(events: readonly Trace[]): Trace[] {
  return events.filter(
    (event) => !event.provenance || event.provenance === "real_run",
  );
}

export type HuntState =
  | { status: "no-run" }
  | { status: "running"; events: Trace[] }
  | { status: "no-evidence"; events: Trace[] }
  | { status: "ready"; events: Trace[]; targets: number[] };

export function huntState(
  target: Selector,
  events: readonly Trace[],
  running: boolean,
): HuntState {
  const own = ownRunEvents(events);
  if (running) return { status: "running", events: own };
  if (!own.length) return { status: "no-run" };
  const targets = selectEvents(target, own);
  return targets.length
    ? { status: "ready", events: own, targets }
    : { status: "no-evidence", events: own };
}

const only = (condition: SelectorCondition, value: unknown): Selector => ({
  event: null,
  round: null,
  path: null,
  span_kind: null,
  name: null,
  [condition]: value,
});

/** 选择器里给出但这一步不满足的条件，逐个用同一个引擎检查。 */
export function unmetConditions(
  target: Selector,
  event: Trace,
): SelectorCondition[] {
  return selectorConditions.filter(
    (condition) =>
      target[condition] != null &&
      !matches(only(condition, target[condition]), event),
  );
}

export type HuntVerdict =
  | { correct: true }
  | { correct: false; unmet: SelectorCondition[] };

export function judgeHunt(target: Selector, event: Trace): HuntVerdict {
  return matches(target, event)
    ? { correct: true }
    : { correct: false, unmet: unmetConditions(target, event) };
}
