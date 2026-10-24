import type { Trace } from "../../../types";

/**
 * Streamed responses (RunContext.complete_stream): a `request` with
 * `data.stream: true`, then `response_delta` events that carry the raw chunks
 * as they arrived, then one `response` the platform assembled from them
 * (`data.stream.assembled_from_chunks`). Everything here reads those events;
 * nothing is typed out or estimated.
 */

export const isStreamDelta = (event: Trace) => event.type === "response_delta";

export const isStreamRequest = (event: Trace) =>
  event.type === "request" && event.data.stream === true;

export interface StreamFacts {
  status: "completed" | "stopped" | "cancelled" | "error" | string;
  chunkCount: number;
  firstChunkMs: number | null;
  firstTokenMs: number | null;
  cancelReason: string | null;
  discardedAfterCancel: number | null;
  doneMarker: boolean | null;
}

const num = (value: unknown) => (typeof value === "number" ? value : null);

/** The stream facts the server wrote on an assembled `response`; null for any other event. */
export function streamFacts(event: Trace): StreamFacts | null {
  if (event.type !== "response") return null;
  const stream = event.data.stream as Record<string, unknown> | undefined;
  if (!stream || stream.assembled_from_chunks !== true) return null;
  return {
    status: typeof stream.status === "string" ? stream.status : "unknown",
    chunkCount: num(stream.chunk_count) ?? 0,
    firstChunkMs: num(stream.first_chunk_ms),
    firstTokenMs: num(stream.first_token_ms),
    cancelReason:
      typeof stream.cancel_reason === "string" ? stream.cancel_reason : null,
    discardedAfterCancel: num(stream.discarded_after_cancel),
    doneMarker:
      typeof stream.done_marker === "boolean" ? stream.done_marker : null,
  };
}

/** Chunk numbers a delta event covers, as the server numbered them. */
export function deltaRange(event: Trace): [number, number] | null {
  const range = event.data.chunk_range;
  return Array.isArray(range) &&
    range.length === 2 &&
    range.every((n) => typeof n === "number")
    ? [range[0] as number, range[1] as number]
    : null;
}

export interface StreamProgress {
  /** Index (in the given events) of the streamed request. */
  requestIndex: number;
  /** Text of the first choice received so far, joined from the delta events. */
  text: string;
  reasoning: string;
  chunks: number;
  deltas: number;
  /** ms from sending to the first chunk, from the first delta's server timing. */
  firstChunkMs: number | null;
  /** The assembled response arrived (the stream ended one way or another). */
  finished: boolean;
  facts: StreamFacts | null;
}

const branchOf = (event: Trace) =>
  typeof event.data.branch === "string" ? event.data.branch : null;

/**
 * The latest streamed request among `events` (the events up to the replay
 * cursor) and what has arrived for it so far. Null when the run streamed nothing.
 */
export function streamProgress(
  events: readonly Trace[],
): StreamProgress | null {
  const requestIndex = events.findLastIndex(isStreamRequest);
  if (requestIndex < 0) return null;
  const branch = branchOf(events[requestIndex]);
  const progress: StreamProgress = {
    requestIndex,
    text: "",
    reasoning: "",
    chunks: 0,
    deltas: 0,
    firstChunkMs: null,
    finished: false,
    facts: null,
  };
  for (const event of events.slice(requestIndex + 1)) {
    if (branchOf(event) !== branch) continue;
    if (isStreamDelta(event)) {
      progress.deltas++;
      if (typeof event.data.text === "string") progress.text += event.data.text;
      if (typeof event.data.reasoning === "string")
        progress.reasoning += event.data.reasoning;
      const range = deltaRange(event);
      if (range) progress.chunks = range[1];
      if (
        progress.firstChunkMs === null &&
        Array.isArray(event.data.received_ms)
      )
        progress.firstChunkMs = num(event.data.received_ms[0]);
    } else if (event.type === "response") {
      progress.finished = true;
      progress.facts = streamFacts(event);
      break;
    }
  }
  return progress;
}
