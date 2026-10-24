import type { TFunction } from "i18next";
import { describe, expect, it } from "vitest";
import { deriveStage } from "../../../../stage/derive";
import type { Trace } from "../../../../types";
import {
  SHOWN_VECTOR_NUMBERS,
  embeddingFacts,
  isEmbeddingEvent,
  truncateVectors,
} from "../embeddings";
import { printJson, shownValue } from "../jsonLines";
import { eventText } from "../useEventText";

const at = (seconds: number) =>
  new Date(Date.UTC(2026, 9, 20, 0, 0, seconds)).toISOString();

const vector = (size: number, seed: number) =>
  Array.from({ length: size }, (_, index) => seed + index / 1000);

const request: Trace = {
  type: "request",
  round: 1,
  timestamp: at(1),
  data: {
    endpoint: "embeddings",
    representation: "http_body",
    body: { model: "text-embedding-v4", input: ["a", "b", "c"] },
  },
};
const response: Trace = {
  type: "response",
  round: 1,
  timestamp: at(2),
  data: {
    endpoint: "embeddings",
    representation: "http_body",
    duration_ms: 1234,
    body: {
      model: "text-embedding-v4",
      data: [0, 1, 2].map((index) => ({
        index,
        embedding: vector(1024, index),
      })),
      usage: { prompt_tokens: 3, total_tokens: 3 },
    },
  },
};
const chatRequest: Trace = {
  type: "request",
  round: 2,
  timestamp: at(3),
  data: {
    representation: "http_body",
    body: { model: "m", messages: [{ role: "user", content: "q" }] },
  },
};

/** Echoes the key and its parameters, so the test sees exactly what was asked for. */
const fakeT = ((key: string, options?: Record<string, unknown>) =>
  options ? `${key} ${JSON.stringify(options)}` : key) as unknown as TFunction<
  "lab",
  "bench.event"
>;

describe("embedding events", () => {
  it("are recognized only by the recorded endpoint", () => {
    expect(isEmbeddingEvent(request)).toBe(true);
    expect(isEmbeddingEvent(response)).toBe(true);
    expect(isEmbeddingEvent(chatRequest)).toBe(false);
    expect(
      isEmbeddingEvent({ ...request, type: "lesson.report" } as Trace),
    ).toBe(false);
  });

  it("summarize inputs, model and dimensions from the body only", () => {
    expect(embeddingFacts(request)).toEqual({
      count: 3,
      model: "text-embedding-v4",
      dimensions: null,
    });
    const asked = {
      ...request,
      data: {
        ...request.data,
        body: { model: "x", input: ["a"], dimensions: 64 },
      },
    };
    expect(embeddingFacts(asked).dimensions).toBe(64);
    // The response reports the length of the vectors it really returned.
    expect(embeddingFacts(response)).toEqual({
      count: 3,
      model: "text-embedding-v4",
      dimensions: 1024,
    });
  });

  it("get readable labels and summaries in the event list", () => {
    const { label, summary } = eventText(fakeT);
    expect(label(request)).toBe("embeddingRequest");
    expect(label(response)).toBe("embeddingResponse");
    expect(summary(request)).toBe(
      'embeddingRequestSummary {"count":3,"model":"text-embedding-v4","dimensions":"embeddingDefaultDimensions"}',
    );
    expect(summary(response)).toBe(
      'embeddingResponseSummary {"count":3,"dimensions":1024,"seconds":"1.23"}',
    );
    // Chat requests keep their own wording.
    expect(summary(chatRequest)).toBe('request {"round":2}');
    expect(label(chatRequest)).toBe("name.request");
  });
});

describe("truncateVectors", () => {
  const marker = (hidden: number) => `+${hidden}`;

  it("keeps the first numbers of each vector and marks the rest, without touching the record", () => {
    const body = shownValue(response);
    const before = JSON.stringify(body);
    const { value, truncated } = truncateVectors(body, marker);
    expect(truncated).toBe(true);
    const rows = (value as { data: { embedding: unknown[] }[] }).data;
    expect(rows[1].embedding).toEqual([
      ...vector(1024, 1).slice(0, SHOWN_VECTOR_NUMBERS),
      `+${1024 - SHOWN_VECTOR_NUMBERS}`,
    ]);
    expect((value as { usage: unknown }).usage).toEqual({
      prompt_tokens: 3,
      total_tokens: 3,
    });
    expect(JSON.stringify(body)).toBe(before);
    // The printed view stays short: about a dozen lines per vector, not a thousand.
    expect(printJson(value).text.split("\n").length).toBeLessThan(60);
    expect(printJson(body).text.split("\n").length).toBeGreaterThan(3000);
  });

  it("returns short vectors and other arrays unchanged", () => {
    const body = {
      data: [{ embedding: [0.1, 0.2] }],
      input: Array.from({ length: 20 }, (_, index) => `t${index}`),
    };
    const result = truncateVectors(body, marker);
    expect(result).toEqual({ value: body, truncated: false });
    expect(result.value).toBe(body);
    // base64-encoded vectors are strings, shown as recorded.
    const encoded = { data: [{ embedding: "AAAA" }] };
    expect(truncateVectors(encoded, marker).truncated).toBe(false);
  });
});

describe("stage with embedding requests", () => {
  it("pairs them as model spans but keeps them out of the context film", () => {
    const events: Trace[] = [
      {
        type: "run_start",
        round: null,
        timestamp: at(0),
        data: {},
      },
      request,
      response,
      chatRequest,
      {
        type: "response",
        round: 2,
        timestamp: at(4),
        data: { body: { choices: [{ message: { content: "ok" } }] } },
      },
    ];
    const stage = deriveStage(events, events.length);
    expect(stage.nodes.some((node) => node.role === "model")).toBe(true);
    const llm = stage.spans.filter((span) => span.kind === "llm");
    expect(llm.map((span) => [span.startIndex, span.endIndex])).toEqual([
      [1, 2],
      [3, 4],
    ]);
    expect(stage.film.map((round) => round.requestIndex)).toEqual([3]);
    expect(stage.film[0].messages[0].isNew).toBe(false);
  });
});
