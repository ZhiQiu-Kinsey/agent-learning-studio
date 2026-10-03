import type { Trace } from "../../../types";

export type LineRange = { from: number; to: number };

/**
 * Pretty-prints a JSON value exactly like `JSON.stringify(value, null, 2)` and
 * records the lines each value occupies, keyed with the selector path syntax
 * (`messages[0].content`; the root is ""). The inspector uses it to frame one
 * field of the real event without re-parsing the text.
 */
export function printJson(value: unknown): {
  text: string;
  ranges: Map<string, LineRange>;
} {
  const lines: string[] = [];
  const ranges = new Map<string, LineRange>();
  const walk = (
    node: unknown,
    path: string,
    prefix: string,
    depth: number,
    comma: string,
  ) => {
    const pad = "  ".repeat(depth);
    if (node === null || typeof node !== "object") {
      // Same as JSON.stringify inside arrays: undefined, functions and symbols become null.
      const literal = JSON.stringify(node) ?? "null";
      lines.push(pad + prefix + literal + comma);
      ranges.set(path, { from: lines.length - 1, to: lines.length - 1 });
      return;
    }
    const array = Array.isArray(node);
    const entries: [string, unknown][] = array
      ? (node as unknown[]).map((item, index) => [`[${index}]`, item])
      : Object.entries(node as Record<string, unknown>)
          .filter(
            ([, item]) =>
              item !== undefined &&
              typeof item !== "function" &&
              typeof item !== "symbol",
          )
          .map(([key, item]) => [key, item]);
    const [open, close] = array ? ["[", "]"] : ["{", "}"];
    if (!entries.length) {
      lines.push(pad + prefix + open + close + comma);
      ranges.set(path, { from: lines.length - 1, to: lines.length - 1 });
      return;
    }
    const from = lines.push(pad + prefix + open) - 1;
    entries.forEach(([key, item], index) => {
      const childPath = array ? path + key : path ? `${path}.${key}` : key;
      walk(
        item,
        childPath,
        array ? "" : `${JSON.stringify(key)}: `,
        depth + 1,
        index < entries.length - 1 ? "," : "",
      );
    });
    lines.push(pad + close + comma);
    ranges.set(path, { from, to: lines.length - 1 });
  };
  walk(value, "", "", 0, "");
  return { text: lines.join("\n"), ranges };
}

const isExchange = (event: Trace) =>
  event.type === "request" || event.type === "response";

/** What the inspector shows for an event: request / response bodies, otherwise all data. */
export const shownValue = (event: Trace) =>
  isExchange(event) ? event.data.body : event.data;

/**
 * Turns a selector path (relative to the event, e.g. `data.body.messages`)
 * into a path inside the JSON the inspector shows (`messages`), or null when
 * the field lies outside it.
 */
export function shownPath(event: Trace, path: string): string | null {
  const root = isExchange(event) ? "data.body" : "data";
  if (path === root) return "";
  if (path.startsWith(`${root}.`)) return path.slice(root.length + 1);
  if (path.startsWith(`${root}[`)) return path.slice(root.length);
  return null;
}
