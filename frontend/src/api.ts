import type { Trace } from "./types";
import { createParser } from "eventsource-parser";

/** 服务端返回的错误；code 为稳定错误码（新接口提供），detail 为中文说明。 */
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
    super("连接提前结束，未收到完成事件。请检查后端状态。");
    this.name = "StreamInterrupted";
  }
}

async function errorFrom(response: Response, fallback: string) {
  const data = await response.json().catch(() => ({}));
  return new ApiError(
    typeof data.detail === "string"
      ? data.detail
      : `${fallback}（${response.status}）`,
    response.status,
    typeof data.code === "string" ? data.code : undefined,
  );
}

export async function jsonFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) throw await errorFrom(response, "请求失败");
  return response.json();
}

/** Fetch owns the request and cancellation; the parser handles SSE framing. */
export async function readEventStream(
  response: Response,
  onEvent: (event: Trace) => void,
) {
  if (!response.ok) throw await errorFrom(response, "运行失败");
  if (!response.body) throw new Error("浏览器未能读取事件流。");
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

/** 请求停止指定运行的后续步骤；keepalive 用于页面关闭时仍能送达。 */
export function cancelRun(runId: string, keepalive = false) {
  return fetch(`/api/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
    keepalive,
  });
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
  } = {},
) {
  const { signal, retries = 5, retryDelayMs = 400 } = options;
  let lastSeq = 0;
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
        throw new Error(
          "事件流多次中断，未收到完成事件。运行记录仍保存在本机服务端，请检查后端状态。",
        );
      await wait(retryDelayMs * failures, signal);
    }
  }
}
