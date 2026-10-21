import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import type { StudioState } from "../../../hooks/useStudio";
import { Code } from "../../Code";
import { Button } from "../../ui/button";
import { Textarea } from "../../ui/textarea";
import { approvalRecords, remainingMs, type ApprovalRecord } from "./approvals";

/** Real seconds left before the server's deadline, ticking once a second. */
function useRemaining(expiresAt: string | null, ticking: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!ticking) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [ticking]);
  return ticking ? remainingMs(expiresAt, now) : null;
}

const short = (digest: string) =>
  digest.startsWith("sha256:") ? `${digest.slice(0, 19)}…` : digest;

function DecisionForm({
  record,
  studio: s,
}: {
  record: ApprovalRecord;
  studio: StudioState;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "approval" });
  const { request } = record;
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState(() =>
    JSON.stringify(request.payload, null, 2),
  );
  const [editError, setEditError] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<"approve" | "reject" | null>(null);
  const [failure, setFailure] = useState("");
  const left = useRemaining(request.expiresAt, !sent);

  async function send(decision: "approve" | "reject") {
    let editedPayload: Record<string, unknown> | undefined;
    if (decision === "approve" && editing) {
      try {
        const value: unknown = JSON.parse(edited);
        if (!value || typeof value !== "object" || Array.isArray(value))
          throw new Error(t("editNotObject"));
        editedPayload = value as Record<string, unknown>;
      } catch (reason) {
        setEditError(
          reason instanceof SyntaxError
            ? t("editSyntax")
            : reason instanceof Error
              ? reason.message
              : String(reason),
        );
        return;
      }
    }
    setSending(true);
    setFailure("");
    try {
      await s.decide({
        approval_id: request.approvalId,
        decision,
        payload_digest: request.payloadDigest,
        ...(note.trim() ? { note: note.trim() } : {}),
        ...(editedPayload ? { edited_payload: editedPayload } : {}),
      });
      setSent(decision);
    } catch (reason) {
      setFailure(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSending(false);
    }
  }

  if (sent)
    return (
      <p
        className="approval-note"
        role="status"
        data-testid="lab-approval-submitted"
      >
        {t(sent === "approve" ? "sentApprove" : "sentReject")}
      </p>
    );
  return (
    <div className="approval-form">
      {left !== null && (
        <p className="approval-note" data-testid="lab-approval-remaining">
          {t("remaining", { seconds: Math.ceil(left / 1000) })}
        </p>
      )}
      {request.editable && (
        <div className="approval-edit">
          <Button
            variant="ghost"
            size="sm"
            aria-pressed={editing}
            onClick={() => setEditing((value) => !value)}
          >
            {editing ? t("editCancel") : t("edit")}
          </Button>
          {editing && (
            <>
              <label htmlFor={`approval-edit-${request.approvalId}`}>
                {t("editLabel")}
              </label>
              <Textarea
                id={`approval-edit-${request.approvalId}`}
                data-testid="lab-approval-edit"
                className="approval-textarea is-code"
                spellCheck={false}
                value={edited}
                aria-invalid={!!editError || undefined}
                onChange={(event) => {
                  setEdited(event.target.value);
                  setEditError("");
                }}
              />
              <small>{t("editHint")}</small>
              {editError && (
                <small className="approval-error" role="alert">
                  {editError}
                </small>
              )}
            </>
          )}
        </div>
      )}
      <label htmlFor={`approval-note-${request.approvalId}`}>
        {t("noteLabel")}
      </label>
      <Textarea
        id={`approval-note-${request.approvalId}`}
        data-testid="lab-approval-note"
        className="approval-textarea"
        maxLength={2000}
        value={note}
        placeholder={t("notePlaceholder")}
        onChange={(event) => setNote(event.target.value)}
      />
      <div className="approval-actions">
        <Button
          onClick={() => void send("approve")}
          disabled={sending}
          data-testid="lab-approval-approve"
        >
          {editing ? t("approveEdited") : t("approve")}
        </Button>
        <Button
          variant="outline"
          onClick={() => void send("reject")}
          disabled={sending}
          data-testid="lab-approval-reject"
        >
          {t("reject")}
        </Button>
      </div>
      {failure && (
        <p
          className="approval-error"
          role="alert"
          data-testid="lab-approval-error"
        >
          {failure}
        </p>
      )}
    </div>
  );
}

function ApprovalCard({
  record,
  studio: s,
  interactive,
}: {
  record: ApprovalRecord;
  studio: StudioState;
  interactive: boolean;
}) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "approval" });
  const { request, resolution } = record;
  const status = resolution?.outcome ?? "pending";
  const seconds = new Intl.NumberFormat(i18n.language, {
    maximumFractionDigits: 1,
  });
  return (
    <article
      className="approval-card"
      data-status={status}
      data-testid="lab-approval-card"
    >
      <header>
        {resolution?.outcome === "approved" ? (
          <ShieldCheck size={16} aria-hidden="true" />
        ) : (
          <ShieldAlert size={16} aria-hidden="true" />
        )}
        <strong>{t("title", { kind: request.kind })}</strong>
        {request.risk && (
          <span className="approval-badge" data-risk={request.risk}>
            {t(`risk.${request.risk}` as "risk.high", {
              defaultValue: request.risk,
            })}
          </span>
        )}
        <span className="approval-badge" data-status={status}>
          {t(`status.${status}` as "status.pending", { defaultValue: status })}
        </span>
      </header>
      <p className="approval-summary" lang={s.runLocale ?? undefined}>
        {request.summary}
      </p>
      <div className="approval-payload">
        <small>{t("payload")}</small>
        <Code content={JSON.stringify(request.payload, null, 2)} />
        <small title={request.payloadDigest}>
          {t("digest", { digest: short(request.payloadDigest) })}
        </small>
      </div>
      {resolution ? (
        <div className="approval-result" data-testid="lab-approval-readonly">
          <p>
            {t("decided", {
              outcome: t(`status.${resolution.outcome}` as "status.approved", {
                defaultValue: resolution.outcome,
              }),
              by: t(`by.${resolution.decidedBy}` as "by.learner", {
                defaultValue: resolution.decidedBy,
              }),
            })}
            {resolution.waitedMs !== null &&
              ` · ${t("waited", { seconds: seconds.format(resolution.waitedMs / 1000) })}`}
          </p>
          {resolution.note && (
            <p className="approval-note" lang={s.runLocale ?? undefined}>
              {t("noteRecorded", { note: resolution.note })}
            </p>
          )}
          {resolution.edited && resolution.payload && (
            <div className="approval-payload">
              <small>{t("editedPayload")}</small>
              <Code content={JSON.stringify(resolution.payload, null, 2)} />
            </div>
          )}
          <small>{t("readonly")}</small>
        </div>
      ) : interactive ? (
        <DecisionForm key={request.approvalId} record={record} studio={s} />
      ) : (
        <p className="approval-note" data-testid="lab-approval-readonly">
          {t(s.running ? "notLive" : "replayPending")}
        </p>
      )}
    </article>
  );
}

/**
 * Approval cards of the run at the cursor. Only the live run on screen, with
 * its stream attached and the request still open, offers approve / reject;
 * replays, restored runs and recordings show the record read-only.
 */
export function ApprovalPanel({
  studio: s,
  live,
}: {
  studio: StudioState;
  live: boolean;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "approval" });
  const records = approvalRecords(s.visible);
  if (!records.length) return null;
  return (
    <section
      className="approval-panel"
      aria-label={t("region")}
      data-testid="lab-approvals"
    >
      {records.map((record) => (
        <ApprovalCard
          key={`${record.request.approvalId}-${record.requestIndex}`}
          record={record}
          studio={s}
          interactive={
            live &&
            !s.detached &&
            !s.stopping &&
            !s.restored &&
            !!s.runId &&
            record.resolution === null
          }
        />
      ))}
    </section>
  );
}
