import type { Trace } from "../types";
import type { Selector } from "./types.gen";

/**
 * One declarative selector system for observe points, guided replay and
 * trace hunts. It only reads events; when nothing matches, callers must say
 * "this run did not produce this evidence" rather than pointing elsewhere.
 */

const PATH_PART = /[^.[\]]+|\[\d+\]|\[id=[A-Za-z0-9_.:-]+\]/g;

/** The array item a `[id=<value>]` segment names: the first object whose string `id` equals it. */
function keyedIndex(items: unknown[], part: string): number {
  const key = part.slice(4, -1);
  return items.findIndex(
    (item) =>
      !!item &&
      typeof item === "object" &&
      !Array.isArray(item) &&
      Object.hasOwn(item, "id") &&
      (item as { id?: unknown }).id === key,
  );
}

/**
 * Resolves paths like `data.body.choices[0].message.tool_calls[1].function.name`.
 * `[id=<value>]` picks an array item by its `id` instead of its position
 * (`data.metrics[id=last_claim]`), so a report can add or reorder entries
 * without moving the evidence an observe point names.
 */
export function resolvePath(value: unknown, path: string): unknown {
  const parts = path.match(PATH_PART);
  if (!parts) return undefined;
  let current: unknown = value;
  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    if (part.startsWith("[id=")) {
      if (!Array.isArray(current)) return undefined;
      const index = keyedIndex(current, part);
      if (index < 0) return undefined;
      current = current[index];
    } else if (part.startsWith("[")) {
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

/**
 * The same path with every `[id=<value>]` segment replaced by the position it
 * names in `value` (`data.metrics[id=last_claim]` -> `data.metrics[5]`), the
 * form the JSON inspector keys its lines by. Unchanged when it has no keyed
 * segment; undefined when a keyed segment names nothing.
 */
export function positionalPath(value: unknown, path: string): string | undefined {
  if (!path.includes("[id=")) return path;
  const parts = path.match(PATH_PART);
  if (!parts) return undefined;
  let current: unknown = value;
  let out = "";
  for (const part of parts) {
    if (part.startsWith("[id=")) {
      if (!Array.isArray(current)) return undefined;
      const index = keyedIndex(current, part);
      if (index < 0) return undefined;
      out += `[${index}]`;
      current = current[index];
      continue;
    }
    if (part.startsWith("[")) {
      out += part;
      current = Array.isArray(current)
        ? current[Number(part.slice(1, -1))]
        : undefined;
    } else {
      out += out ? `.${part}` : part;
      current =
        current && typeof current === "object" && !Array.isArray(current)
          ? (current as Record<string, unknown>)[part]
          : undefined;
    }
  }
  return out;
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
