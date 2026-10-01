import type { Trace } from "./types";
import { createParser } from "eventsource-parser";

export async function jsonFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `请求失败（${response.status}）`,
    );
  }
  return response.json();
}

/** Fetch owns the request and cancellation; the parser handles SSE framing. */
export async function readEventStream(
  response: Response,
  onEvent: (event: Trace) => void,
) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `运行失败（${response.status}）`,
    );
  }
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
  if (!sawDone)
    throw new Error("连接提前结束，未收到完成事件。请检查后端状态。");
}
