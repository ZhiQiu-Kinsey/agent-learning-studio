import type { Trace } from "./types";
import { createParser } from "eventsource-parser";
import i18n, { sourceLocale } from "./i18n";
import { clientError, errorMessage } from "./i18n/errors";

/** Server error: `code` is stable and translated by the UI; `detail` is the server fallback. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** 事件流在收到 done 之前结束；可以按最后收到的 seq 续读。 */
export class StreamInterrupted extends Error {
  constructor() {
    super(clientError("streamEnded"));
    this.name = "StreamInterrupted";
  }
}

async function errorFrom(
  response: Response,
  fallback: "requestFailed" | "runFailed",
) {
  const data = await response.json().catch(() => ({}));
  const code = typeof data.code === "string" ? data.code : undefined;
  return new ApiError(
    errorMessage(
      code,
      data.params && typeof data.params === "object" ? data.params : undefined,
      typeof data.detail === "string" ? data.detail : undefined,
      clientError(fallback, { status: response.status }),
    ),
    response.status,
    code,
  );
}

/**
 * Content endpoints serve translation overlays; the source locale needs no
 * parameter. Callers that fetch these must refetch when the language changes
 * (see `hooks/useContentLanguage`).
 */
const localizedPaths =
  /^\/api\/(lessons(\/[^/?]+(\/code)?)?|onboarding|curriculum|glossary)(\?|$)/;
export function withLocale(path: string, language?: string) {
  language ??= contentLanguage();
  if (language === sourceLocale || !localizedPaths.test(path)) return path;
  return `${path}${path.includes("?") ? "&" : "?"}lang=${encodeURIComponent(language)}`;
}

/** The language content requests ask for right now (the UI language). */
export function contentLanguage() {
  return i18n.resolvedLanguage ?? i18n.language ?? sourceLocale;
}

/** `language` pins a localized request to the language its caller keys it by. */
export async function jsonFetch<T>(
  path: string,
  init?: RequestInit,
  language?: string,
): Promise<T> {
  const response = await fetch(withLocale(path, language), init);
  if (!response.ok) throw await errorFrom(response, "requestFailed");
  return response.json();
}

/** Fetch owns the request and cancellation; the parser handles SSE framing. */
export async function readEventStream(
  response: Response,
  onEvent: (event: Trace) => void,
) {
  if (!response.ok) throw await errorFrom(response, "runFailed");
  if (!response.body) throw new Error(clientError("noStream"));
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let sawDone = false;
  const parser = createParser({
    onEvent(message) {
      if (!message.data) return;
      const event = JSON.parse(message.data) as Trace;
      onEvent(event);
      if (event.type === "done") sawDone = true;
    },
  });
  try {
    while (true) {
      const { done, value } = await reader.read();
      parser.feed(decoder.decode(value, { stream: !done }));
      if (done) {
        // Preserve the existing handling of a final event without a blank line.
        parser.feed("\n\n");
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
  if (!sawDone) throw new StreamInterrupted();
}

export type RunRequest = {
  lesson_id: string;
  mode: "live";
  question: string;
  exercise_id: string;
  inputs: Record<string, unknown>;
  /**
   * The UI language. The server runs the lesson in it when the lesson supports
   * it, otherwise in the source language, and records the result in run_start.
   */
  locale: string;
};

/** 创建运行；服务端在后台执行，返回 run_id 后再订阅事件。 */
export async function createRun(payload: RunRequest, signal?: AbortSignal) {
  const { run_id } = await jsonFetch<{ run_id: string }>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  return run_id;
}

/**
 * Why a run is asked to stop, recorded in the run's events (`done.data.cancel_reason`):
 * the Stop button or the page going away. Closing only the event stream is not a stop.
 */
export type CancelReason = "user_stop" | "page_closed";

/** 请求停止指定运行的后续步骤；keepalive 用于页面关闭时仍能送达。 */
export function cancelRun(
  runId: string,
  keepalive = false,
  reason: CancelReason = keepalive ? "page_closed" : "user_stop",
) {
  return fetch(`/api/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
    keepalive,
  });
}

export type ApprovalSubmission = {
  approval_id: string;
  decision: "approve" | "reject";
  /** Must equal the request's digest: the decision is about the payload on screen. */
  payload_digest: string;
  note?: string;
  /** Only for an editable request, only with approve. */
  edited_payload?: Record<string, unknown>;
};

/** A person's decision on the run's pending approval; the run records it as an event. */
export async function submitApproval(
  runId: string,
  submission: ApprovalSubmission,
) {
  return jsonFetch<{ status: string }>(
    `/api/runs/${encodeURIComponent(runId)}/approvals`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(submission),
    },
  );
}

/** Starts a new run from a checkpoint of a finished run; returns the new run id. */
export async function resumeRun(runId: string, checkpointId: string) {
  const { run_id } = await jsonFetch<{ run_id: string }>(
    `/api/runs/${encodeURIComponent(runId)}/resume`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ checkpoint_id: checkpointId }),
    },
  );
  return run_id;
}

function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = window.setTimeout(() => {
      signal?.removeEventListener("abort", stop);
      resolve();
    }, ms);
    const stop = () => {
      window.clearTimeout(timer);
      reject(signal?.reason);
    };
    signal?.addEventListener("abort", stop, { once: true });
  });
}

const retryable = (reason: unknown) =>
  !(reason instanceof ApiError && reason.status < 500);

/**
 * 读取运行事件直到 done。断线后按最后收到的 seq 续读：服务端从 from_seq 回放，
 * 客户端再按 seq 去重，因此不会重复也不会遗漏。连续多次没有进展才放弃。
 */
export async function followRunEvents(
  runId: string,
  onEvent: (event: Trace) => void,
  options: {
    signal?: AbortSignal;
    retries?: number;
    retryDelayMs?: number;
    /** Continue after events already on screen (reconnecting after a detach). */
    fromSeq?: number;
  } = {},
) {
  const { signal, retries = 5, retryDelayMs = 400, fromSeq = 1 } = options;
  let lastSeq = Math.max(0, fromSeq - 1);
  let failures = 0;
  while (true) {
    const before = lastSeq;
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/events?from_seq=${lastSeq + 1}`,
        { signal, headers: { Accept: "text/event-stream" } },
      );
      await readEventStream(response, (event) => {
        if (typeof event.seq === "number") {
          if (event.seq <= lastSeq) return;
          lastSeq = event.seq;
        }
        onEvent(event);
      });
      return lastSeq;
    } catch (reason) {
      if (signal?.aborted || !retryable(reason)) throw reason;
      failures = lastSeq > before ? 1 : failures + 1;
      if (failures > retries)
        throw new Error(clientError("streamRetriesExhausted"));
      await wait(retryDelayMs * failures, signal);
    }
  }
}
