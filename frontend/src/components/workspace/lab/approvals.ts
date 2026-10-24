import type { Trace } from "../../../types";

/**
 * Approval gates (RunContext.request_approval): `approval_requested` pauses the
 * run, `approval_resolved` records how it ended. Pairs are read from the events
 * only; whether the page may still decide is the caller's business (a live run
 * on screen), never inferred from a replay.
 */

export interface ApprovalRequest {
  approvalId: string;
  kind: string;
  summary: string;
  payload: Record<string, unknown>;
  payloadDigest: string;
  risk: string | null;
  editable: boolean;
  timeoutS: number | null;
  expiresAt: string | null;
}

export interface ApprovalResolution {
  outcome: "approved" | "rejected" | "timeout" | "cancelled" | string;
  decidedBy: string;
  note: string | null;
  edited: boolean;
  payload: Record<string, unknown> | null;
  payloadDigest: string | null;
  waitedMs: number | null;
}

export interface ApprovalRecord {
  request: ApprovalRequest;
  requestIndex: number;
  resolution: ApprovalResolution | null;
  resolvedIndex: number | null;
}

const text = (value: unknown) => (typeof value === "string" ? value : "");
const object = (value: unknown) =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

export function approvalRequestOf(event: Trace): ApprovalRequest | null {
  if (event.type !== "approval_requested") return null;
  const data = event.data;
  return {
    approvalId: text(data.approval_id),
    kind: text(data.kind),
    summary: text(data.summary),
    payload: object(data.payload) ?? {},
    payloadDigest: text(data.payload_digest),
    risk: typeof data.risk === "string" ? data.risk : null,
    editable: data.editable === true,
    timeoutS: typeof data.timeout_s === "number" ? data.timeout_s : null,
    expiresAt: typeof data.expires_at === "string" ? data.expires_at : null,
  };
}

export function approvalResolutionOf(event: Trace): ApprovalResolution | null {
  if (event.type !== "approval_resolved") return null;
  const data = event.data;
  return {
    outcome: text(data.outcome),
    decidedBy: text(data.decided_by),
    note: typeof data.note === "string" ? data.note : null,
    edited: data.edited === true,
    payload: object(data.payload),
    payloadDigest:
      typeof data.payload_digest === "string" ? data.payload_digest : null,
    waitedMs: typeof data.waited_ms === "number" ? data.waited_ms : null,
  };
}

/** Every approval among `events`, in request order, paired by approval_id. */
export function approvalRecords(events: readonly Trace[]): ApprovalRecord[] {
  const records: ApprovalRecord[] = [];
  const open = new Map<string, ApprovalRecord>();
  events.forEach((event, index) => {
    const request = approvalRequestOf(event);
    if (request) {
      const record = {
        request,
        requestIndex: index,
        resolution: null,
        resolvedIndex: null,
      };
      records.push(record);
      open.set(request.approvalId, record);
      return;
    }
    const resolution = approvalResolutionOf(event);
    const id = text(event.data.approval_id);
    const record = resolution ? open.get(id) : undefined;
    if (record && resolution) {
      record.resolution = resolution;
      record.resolvedIndex = index;
      open.delete(id);
    }
  });
  return records;
}

/** The request still waiting for a decision among `events`, if any. */
export const pendingApproval = (events: readonly Trace[]) =>
  approvalRecords(events).findLast((record) => record.resolution === null) ??
  null;

/** Real time left before the server's own deadline; null when unknown. */
export function remainingMs(expiresAt: string | null, now: number) {
  if (!expiresAt) return null;
  const end = Date.parse(expiresAt);
  return Number.isFinite(end) ? Math.max(0, end - now) : null;
}

/** The checkpoint a `checkpoint` event saved. */
export function checkpointOf(event: Trace) {
  if (event.type !== "checkpoint") return null;
  const id = text(event.data.checkpoint_id);
  return id ? { id, name: text(event.data.name) } : null;
}

/** Where a resumed run started from (`run_start.data.resumed_from`). */
export function resumedFromOf(events: readonly Trace[]) {
  const start = events.find((event) => event.type === "run_start");
  const from = object(start?.data.resumed_from);
  return from && typeof from.run_id === "string"
    ? {
        runId: from.run_id,
        checkpointId: text(from.checkpoint_id),
        name: text(from.name),
      }
    : null;
}
