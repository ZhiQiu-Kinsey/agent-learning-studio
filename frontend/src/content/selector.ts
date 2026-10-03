import type { Trace } from "../types";
import type { Selector } from "./types.gen";

/**
 * One declarative selector system for observe points, guided replay and
 * trace hunts. It only reads events; when nothing matches, callers must say
 * "this run did not produce this evidence" rather than pointing elsewhere.
 */

/** Resolves paths like `data.body.choices[0].message.tool_calls[1].function.name`. */
export function resolvePath(value: unknown, path: string): unknown {
  const parts = path.match(/[^.[\]]+|\[\d+\]/g);
  if (!parts) return undefined;
  let current: unknown = value;
  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    if (part.startsWith("[")) {
      if (!Array.isArray(current)) return undefined;
      current = current[Number(part.slice(1, -1))];
    } else {
      if (typeof current !== "object" || Array.isArray(current))
        return undefined;
      if (!Object.hasOwn(current, part)) return undefined;
      current = (current as Record<string, unknown>)[part];
    }
  }
  return current;
}

/** Tool name as the `name` condition sees it: call payload first, then result. */
export function toolNameOf(event: Trace): string | undefined {
  const fn = event.data.function as { name?: unknown } | undefined;
  if (fn && typeof fn.name === "string") return fn.name;
  return typeof event.data.name === "string" ? event.data.name : undefined;
}

/**
 * Whether one event meets every condition. `nth` is not a condition: a single
 * event cannot know its rank among the hits, so only `selectEvents` and
 * `findEvidence` apply it.
 */
export function matches(selector: Selector, event: Trace): boolean {
  if (selector.event != null && event.type !== selector.event) return false;
  if (selector.round != null && event.round !== selector.round) return false;
  if (selector.span_kind != null && event.span_kind !== selector.span_kind)
    return false;
  if (selector.name != null && toolNameOf(event) !== selector.name)
    return false;
  if (selector.path != null && resolvePath(event, selector.path) === undefined)
    return false;
  return true;
}

/**
 * Indices of matching events, in run order. With `nth` (1-based) only that
 * hit is left, or none when the run has fewer hits.
 */
export function selectEvents(
  selector: Selector,
  events: readonly Trace[],
): number[] {
  const hits = events.flatMap((event, index) =>
    matches(selector, event) ? [index] : [],
  );
  if (selector.nth == null) return hits;
  const hit = hits[selector.nth - 1];
  return hit === undefined ? [] : [hit];
}

export type Evidence =
  { found: true; index: number; value: unknown } | { found: false };

/**
 * The first selected event at or after `from`, and the value at the
 * selector's path, so a guide can seek to it and highlight that JSON node.
 * `nth` counts over the whole run, not from `from`.
 */
export function findEvidence(
  selector: Selector,
  events: readonly Trace[],
  from = 0,
): Evidence {
  const index = selectEvents(selector, events).find((hit) => hit >= from);
  if (index === undefined) return { found: false };
  const event = events[index];
  return {
    found: true,
    index,
    value: selector.path != null ? resolvePath(event, selector.path) : event,
  };
}
