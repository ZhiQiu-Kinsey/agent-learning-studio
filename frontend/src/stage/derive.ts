/**
 * Agent Stage: a pure projection of real events at a cursor position.
 *
 * - Topology comes from ALL events (nodes do not pop in during replay); activity
 *   comes only from events before the cursor.
 * - Spans pair start/end events by the server's span_id (v2) or by the shared
 *   SPAN_EVENTS rules (v1 fallback). Durations come only from server timestamps.
 * - A stop leaves completed results intact; only tool calls still open are
 *   marked "stopped" (no result). Nothing here invents a value an event lacks.
 */
import { spanRuleFor } from "../trace";
import type { Provenance, Trace } from "../types";

export type NodeRole = "user" | "runtime" | "model" | "tool" | "memory";
export type NodeState =
  "dormant" | "idle" | "active" | "waiting" | "error" | "stopped";
export type RunStatus =
  "idle" | "running" | "completed" | "error" | "cancelled";

export interface StageNode {
  id: string;
  role: NodeRole;
  /** Tool name for tool nodes; other labels come from the UI's translations. */
  name?: string;
  state: NodeState;
}

export interface StageEdge {
  id: string;
  from: string;
  to: string;
}

export interface StageSignal {
  edge: string;
  /** Index of the event that fired it; one real event fires exactly one signal. */
  eventIndex: number;
}

export interface StageSpan {
  id: string;
  kind: "llm" | "tool";
  round: number | null;
  name?: string;
  startIndex: number;
  endIndex: number | null;
  startAt: string;
  endAt: string | null;
  /** From server timestamps only; null while open or when a timestamp is unreadable. */
  durationMs: number | null;
  status: "open" | "closed" | "stopped";
  ok?: boolean;
}

export interface FilmMessage {
  role: string;
  chars: number;
  isNew: boolean;
}

export interface FilmRound {
  round: number | null;
  requestIndex: number;
  messages: FilmMessage[];
  /** Usage exactly as the response reported it; null when it reported none. */
  usage: Record<string, unknown> | null;
}

export interface StageState {
  nodes: StageNode[];
  edges: StageEdge[];
  signal: StageSignal | null;
  spans: StageSpan[];
  film: FilmRound[];
  status: RunStatus;
  provenance: Provenance | "unknown";
  cursor: number;
}

const toolNodeId = (name: string) => `tool:${name}`;
const isMemoryEvent = (type: string) =>
  type === "lesson.memory" || type === "lesson.state";

function toolName(event: Trace): string {
  const { data } = event;
  const fn = data.function as { name?: unknown } | undefined;
  if (fn && typeof fn.name === "string") return fn.name;
  return typeof data.name === "string" ? data.name : "tool";
}

function edgeFor(
  event: Trace,
  toolOfCall: Map<string, string>,
): [string, string] | null {
  switch (event.type) {
    case "run_start":
      return ["user", "runtime"];
    case "request":
      return ["runtime", "model"];
    case "response":
      return ["model", "runtime"];
    case "tool_call":
      return ["runtime", toolNodeId(toolName(event))];
    case "tool_result": {
      const callId = event.data.tool_call_id;
      const name =
        (typeof callId === "string" && toolOfCall.get(callId)) ||
        toolName(event);
      return [toolNodeId(name), "runtime"];
    }
    case "answer":
      return ["runtime", "user"];
    default:
      return isMemoryEvent(event.type) ? ["runtime", "memory"] : null;
  }
}

function elapsed(start: string, end: string): number | null {
  const ms = Date.parse(end) - Date.parse(start);
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

const textLength = (content: unknown) =>
  typeof content === "string"
    ? content.length
    : content == null
      ? 0
      : JSON.stringify(content).length;

function requestMessages(event: Trace): unknown[] {
  const body = event.data.body as { messages?: unknown } | undefined;
  return Array.isArray(body?.messages) ? body.messages : [];
}

function responseUsage(
  event: Trace | undefined,
): Record<string, unknown> | null {
  const body = event?.data.body as { usage?: unknown } | undefined;
  return body?.usage && typeof body.usage === "object"
    ? (body.usage as Record<string, unknown>)
    : null;
}

export function deriveStage(
  events: readonly Trace[],
  cursor: number,
): StageState {
  const at = Math.max(0, Math.min(cursor, events.length));
  const visible = events.slice(0, at);

  // Topology from the whole run.
  const toolOfCall = new Map<string, string>();
  const toolNames: string[] = [];
  let hasModel = false;
  let hasMemory = false;
  for (const event of events) {
    if (event.type === "request") hasModel = true;
    if (isMemoryEvent(event.type)) hasMemory = true;
    if (event.type === "tool_call") {
      const name = toolName(event);
      if (typeof event.data.id === "string")
        toolOfCall.set(event.data.id, name);
      if (!toolNames.includes(name)) toolNames.push(name);
    }
  }
  const nodes: StageNode[] = events.length
    ? [
        { id: "user", role: "user", state: "dormant" },
        { id: "runtime", role: "runtime", state: "dormant" },
        ...(hasModel
          ? [{ id: "model", role: "model" as const, state: "dormant" as const }]
          : []),
        ...toolNames.map((name) => ({
          id: toolNodeId(name),
          role: "tool" as const,
          name,
          state: "dormant" as const,
        })),
        ...(hasMemory
          ? [
              {
                id: "memory",
                role: "memory" as const,
                state: "dormant" as const,
              },
            ]
          : []),
      ]
    : [];
  const edges = new Map<string, StageEdge>();
  for (const event of events) {
    const pair = edgeFor(event, toolOfCall);
    if (pair) {
      const id = `${pair[0]}->${pair[1]}`;
      edges.set(id, { id, from: pair[0], to: pair[1] });
    }
  }

  // Spans and activity from visible events.
  const spans: StageSpan[] = [];
  const openByKey = new Map<string, StageSpan>();
  const openLlm: StageSpan[] = [];
  let status = (visible.length ? "running" : "idle") as RunStatus;
  let signal: StageSignal | null = null;
  const touched = new Set<string>();
  const failedTools = new Set<string>();
  let runtimeError = false;

  visible.forEach((event, index) => {
    const pair = edgeFor(event, toolOfCall);
    if (pair) {
      signal = { edge: `${pair[0]}->${pair[1]}`, eventIndex: index };
      touched.add(pair[0]).add(pair[1]);
    } else if (index === visible.length - 1) signal = null;

    const rule = spanRuleFor(event.type);
    if (rule.span_kind === "llm" || rule.span_kind === "tool") {
      const kind = rule.span_kind;
      const pairValue =
        kind === "tool" && rule.pair_field
          ? event.data[rule.pair_field]
          : undefined;
      const key =
        event.span_id ??
        (kind === "tool" && typeof pairValue === "string"
          ? `tool:${pairValue}`
          : undefined);
      if (rule.phase === "start") {
        const span: StageSpan = {
          id: key ?? `${kind}-${index}`,
          kind,
          round: event.round,
          ...(kind === "tool" ? { name: toolName(event) } : {}),
          startIndex: index,
          endIndex: null,
          startAt: event.timestamp,
          endAt: null,
          durationMs: null,
          status: "open",
        };
        spans.push(span);
        if (kind === "llm" && !key) openLlm.push(span);
        else openByKey.set(span.id, span);
      } else if (rule.phase === "end") {
        const span = key
          ? openByKey.get(key)
          : kind === "llm"
            ? openLlm.shift()
            : undefined;
        if (span) {
          if (key) openByKey.delete(key);
          span.endIndex = index;
          span.endAt = event.timestamp;
          span.durationMs = elapsed(span.startAt, event.timestamp);
          span.status = "closed";
          if (kind === "tool") {
            const result = event.data.result as { ok?: unknown } | undefined;
            if (typeof result?.ok === "boolean") span.ok = result.ok;
            if (result?.ok === false)
              failedTools.add(toolNodeId(span.name ?? toolName(event)));
            else failedTools.delete(toolNodeId(span.name ?? toolName(event)));
          }
        }
      }
    }
    if (event.type === "error") runtimeError = true;
    if (event.type === "done") {
      const value = event.data.status;
      status =
        value === "cancelled"
          ? "cancelled"
          : value === "error" || runtimeError
            ? "error"
            : "completed";
    }
  });

  if (status === "cancelled")
    for (const span of spans)
      if (span.status === "open") span.status = "stopped";

  const openTools = new Set(
    spans
      .filter((span) => span.kind === "tool" && span.status === "open")
      .map((span) => toolNodeId(span.name!)),
  );
  const stoppedTools = new Set(
    spans
      .filter((span) => span.kind === "tool" && span.status === "stopped")
      .map((span) => toolNodeId(span.name!)),
  );
  const modelWaiting = spans.some(
    (span) => span.kind === "llm" && span.status === "open",
  );
  for (const node of nodes) {
    if (!touched.has(node.id)) continue;
    node.state = stoppedTools.has(node.id)
      ? "stopped"
      : openTools.has(node.id)
        ? "active"
        : failedTools.has(node.id)
          ? "error"
          : node.id === "model" && modelWaiting
            ? "waiting"
            : node.id === "runtime" && runtimeError
              ? "error"
              : node.id === "runtime" && status === "running"
                ? "active"
                : "idle";
  }

  // Context film: what each request actually sent, with new items marked.
  const film: FilmRound[] = [];
  let previous: string[] = [];
  visible.forEach((event, index) => {
    if (event.type !== "request") return;
    const messages = requestMessages(event);
    const serialized = messages.map((message) => JSON.stringify(message));
    let shared = 0;
    while (
      shared < previous.length &&
      shared < serialized.length &&
      previous[shared] === serialized[shared]
    )
      shared++;
    const span = spans.find(
      (item) => item.kind === "llm" && item.startIndex === index,
    );
    film.push({
      round: event.round,
      requestIndex: index,
      messages: messages.map((message, position) => {
        const item = (message ?? {}) as {
          role?: unknown;
          content?: unknown;
          tool_calls?: unknown;
        };
        return {
          role: typeof item.role === "string" ? item.role : "unknown",
          chars: textLength(item.content) + textLength(item.tool_calls),
          isNew: film.length > 0 && position >= shared,
        };
      }),
      usage:
        span?.endIndex != null ? responseUsage(visible[span.endIndex]) : null,
    });
    previous = serialized;
  });

  const first = events.find((event) => event.provenance);
  return {
    nodes,
    edges: [...edges.values()],
    signal,
    spans,
    film,
    status,
    provenance: first?.provenance ?? "unknown",
    cursor: at,
  };
}
