import type { Trace } from "../../../types";

/** Numbers of each vector the inspector shows before it truncates the display. */
export const SHOWN_VECTOR_NUMBERS = 8;

/** A request / response the server recorded with `data.endpoint: "embeddings"`. */
export const isEmbeddingEvent = (event: Trace) =>
  (event.type === "request" || event.type === "response") &&
  event.data.endpoint === "embeddings";

export interface EmbeddingFacts {
  /** Inputs of a request, or vectors of a response. */
  count: number;
  model: string | null;
  /**
   * Request: the `dimensions` it asked for (null = provider default).
   * Response: the length of the first vector actually returned (null = none).
   */
  dimensions: number | null;
}

const bodyOf = (event: Trace) =>
  (event.data.body ?? {}) as Record<string, unknown>;

/** What a reader needs at a glance, read only from the recorded body. */
export function embeddingFacts(event: Trace): EmbeddingFacts {
  const body = bodyOf(event);
  const model = typeof body.model === "string" ? body.model : null;
  if (event.type === "request") {
    const input = body.input;
    return {
      count: Array.isArray(input)
        ? input.length
        : typeof input === "string"
          ? 1
          : 0,
      model,
      dimensions: typeof body.dimensions === "number" ? body.dimensions : null,
    };
  }
  const data = Array.isArray(body.data) ? body.data : [];
  const first = data[0] as { embedding?: unknown } | undefined;
  return {
    count: data.length,
    model,
    dimensions: Array.isArray(first?.embedding) ? first.embedding.length : null,
  };
}

/**
 * A copy of an embeddings response body for display: every `embedding` array
 * longer than `keep` keeps its first `keep` numbers plus one marker string
 * (`marker(hidden)`). The recorded event is never changed; copy and the full
 * view use the original. Bodies without long vectors come back as they are.
 */
export function truncateVectors(
  body: unknown,
  marker: (hidden: number) => string,
  keep = SHOWN_VECTOR_NUMBERS,
): { value: unknown; truncated: boolean } {
  let truncated = false;
  const walk = (node: unknown, key: string | null): unknown => {
    if (Array.isArray(node)) {
      if (
        key === "embedding" &&
        node.length > keep &&
        node.every((item) => typeof item === "number")
      ) {
        truncated = true;
        return [...node.slice(0, keep), marker(node.length - keep)];
      }
      return node.map((item) => walk(item, null));
    }
    if (node && typeof node === "object")
      return Object.fromEntries(
        Object.entries(node as Record<string, unknown>).map(([name, item]) => [
          name,
          walk(item, name),
        ]),
      );
    return node;
  };
  const value = walk(body, null);
  return truncated ? { value, truncated } : { value: body, truncated };
}
