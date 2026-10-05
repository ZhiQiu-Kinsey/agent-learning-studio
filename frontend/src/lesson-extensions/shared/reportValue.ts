/**
 * How one value of a `lesson.report` shows on the evidence board. The value is
 * never rewritten, only laid out: numbers stay big tiles, words use body text,
 * objects (a provider's usage, say) become key-value rows, long text folds.
 */
export type ReportValue =
  | { kind: "number"; text: string }
  | { kind: "text"; text: string }
  | { kind: "long"; text: string }
  | { kind: "pairs"; pairs: { key: string; value: string }[] }
  | { kind: "empty" };

/** Up to this many characters a string still fits a metric tile. */
export const SHORT_TEXT = 32;
/** Longer cell text starts folded in the table. */
export const LONG_CELL = 160;

/** "42", "-1.5", "80%", "3/5": numbers written as text still read as numbers. */
const NUMBER_LIKE = /^[-+]?\d[\d.,]*(?:\s?%|\s?\/\s?\d[\d.,]*)?$/;

const plainObject = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);

/** Nested keys joined with dots; arrays and leaves written as JSON text. */
function flatten(
  value: Record<string, unknown>,
  prefix = "",
): { key: string; value: string }[] {
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (plainObject(item) && Object.keys(item).length)
      return flatten(item, path);
    return [
      {
        key: path,
        value: typeof item === "string" ? item : (JSON.stringify(item) ?? ""),
      },
    ];
  });
}

/**
 * A string holding a JSON object (older runs carry usage that way) is shown as
 * the same key-value rows; anything else stays the text it is.
 */
function jsonObject(text: string): Record<string, unknown> | null {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    return plainObject(parsed) && Object.keys(parsed).length ? parsed : null;
  } catch {
    return null;
  }
}

export function reportValue(value: unknown, longAt = SHORT_TEXT): ReportValue {
  if (typeof value === "number" || typeof value === "boolean")
    return { kind: "number", text: String(value) };
  if (plainObject(value))
    return Object.keys(value).length
      ? { kind: "pairs", pairs: flatten(value) }
      : { kind: "empty" };
  if (Array.isArray(value))
    return { kind: "long", text: JSON.stringify(value) };
  if (typeof value !== "string") return { kind: "empty" };
  if (NUMBER_LIKE.test(value.trim())) return { kind: "number", text: value };
  const object = jsonObject(value);
  if (object) return { kind: "pairs", pairs: flatten(object) };
  return value.length > longAt || value.includes("\n")
    ? { kind: "long", text: value }
    : { kind: "text", text: value };
}

/** Compact tiles first (numbers, short words), wide entries after, each keeping report order. */
export function splitMetrics<T extends { value?: unknown }>(
  metrics: readonly T[],
) {
  const shaped = metrics.map((metric, index) => ({
    metric,
    index,
    shown: reportValue(metric.value),
  }));
  const compact = (kind: ReportValue["kind"]) =>
    kind === "number" || kind === "text" || kind === "empty";
  return {
    tiles: shaped.filter((item) => compact(item.shown.kind)),
    wide: shaped.filter((item) => !compact(item.shown.kind)),
  };
}
