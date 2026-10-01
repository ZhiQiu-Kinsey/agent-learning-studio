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

function toolNameOf(event: Trace): string | undefined {
  const fn = event.data.function as { name?: unknown } | undefined;
  if (fn && typeof fn.name === "string") return fn.name;
  return typeof event.data.name === "string" ? event.data.name : undefined;
}

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

/** Indices of matching events, in run order. */
export function selectEvents(
  selector: Selector,
  events: readonly Trace[],
): number[] {
  return events.flatMap((event, index) =>
    matches(selector, event) ? [index] : [],
  );
}

export type Evidence =
  { found: true; index: number; value: unknown } | { found: false };

/**
 * First matching event (optionally at or after `from`) and the value at the
 * selector's path, so a guide can seek to it and highlight that JSON node.
 */
export function findEvidence(
  selector: Selector,
  events: readonly Trace[],
  from = 0,
): Evidence {
  for (let index = Math.max(0, from); index < events.length; index++) {
    const event = events[index];
    if (matches(selector, event))
      return {
        found: true,
        index,
        value:
          selector.path != null ? resolvePath(event, selector.path) : event,
      };
  }
  return { found: false };
}
