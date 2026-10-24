import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, Check, Code2, Copy, RotateCcw } from "lucide-react";
import { useReducedMotion } from "../../../motion";
import type { StudioState } from "../../../hooks/useStudio";
import type { Trace } from "../../../types";
import TextType from "../../react-bits/TextType";
import { Code } from "../../Code";
import { Button } from "../../ui/button";
import {
  SHOWN_VECTOR_NUMBERS,
  isEmbeddingEvent,
  truncateVectors,
} from "./embeddings";
import { checkpointOf } from "./approvals";
import { useEvidenceFocus } from "./evidenceFocus";
import { isStreamDelta, streamFacts } from "./streaming";
import { printJson, shownPath, shownValue } from "./jsonLines";
import { useEventText } from "./useEventText";

const isExchange = (e: Trace) => e.type === "request" || e.type === "response";

function EmptyDetail({ active }: { active: boolean }) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.detail" });
  const reducedMotion = useReducedMotion();
  return (
    <div className="inspector-empty">
      <div>
        <Code2 size={28} />
      </div>
      <h3 aria-label={t("emptyTitle")}>
        {active ? (
          <TextType
            text={t("emptyTitle")}
            typingSpeed={90}
            startOnVisible
            loop={false}
            showCursor={!reducedMotion}
            aria-hidden="true"
          />
        ) : (
          t("emptyTitle")
        )}
      </h3>
      <p>
        {t("emptyLine1")}
        <br />
        {t("emptyLine2")}
      </p>
      <div className="empty-flow">
        <span>{t("flowQuestion")}</span>
        <ArrowRight size={13} />
        <span>{t("flowModel")}</span>
        <ArrowRight size={13} />
        <span>{t("flowTool")}</span>
      </div>
    </div>
  );
}

/**
 * A checkpoint of the learner's own finished run can start a new run from it.
 * Nothing of the old run is replayed: the new run's requests are new requests.
 */
function ResumeFromCheckpoint({
  studio: s,
  event,
}: {
  studio: StudioState;
  event: Trace;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.detail" });
  const checkpoint = checkpointOf(event);
  if (!checkpoint || !s.runId || s.running) return null;
  return (
    <p className="event-explanation event-resume">
      <span>{t("resumeHint")}</span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => void s.resume(checkpoint.id)}
        data-testid="lab-resume-button"
      >
        <RotateCcw size={14} aria-hidden="true" />
        {t("resume", { name: checkpoint.name || checkpoint.id })}
      </Button>
    </p>
  );
}

/**
 * Inspector for the selected event: its complete JSON, labelled honestly as
 * SDK-standardised data or HTTP data, with a copy button. When the lab points
 * at a field of this event (guided replay, "locate"), those lines are framed.
 */
export function EventDetail({
  studio: s,
  active,
  copied,
  onCopied,
}: {
  studio: StudioState;
  /** The lab scene is on screen. */
  active: boolean;
  copied: boolean;
  onCopied: () => void;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.detail" });
  const { label } = useEventText();
  const reducedMotion = useReducedMotion();
  const focus = useEvidenceFocus();
  const markRef = useRef<HTMLElement>(null);
  const revealed = useRef<typeof focus>(null);
  const event = s.active;
  const body = event ? shownValue(event) : null;
  const activeIndex = event ? s.visible.indexOf(event) : -1;
  // Embedding vectors run to thousands of numbers: the view keeps the first few of each
  // and says so; the record, the copy button and "show full JSON" keep every number.
  const [fullIndex, setFullIndex] = useState<number | null>(null);
  const embedding = event ? isEmbeddingEvent(event) : false;
  const shortened = useMemo(
    () =>
      embedding
        ? truncateVectors(body, (hidden) =>
            t("embeddingHidden", { count: hidden }),
          )
        : { value: body, truncated: false },
    [body, embedding, t],
  );
  const showFull = fullIndex === activeIndex;
  const shown = shortened.truncated && !showFull ? shortened.value : body;
  const printed = useMemo(() => printJson(shown), [shown]);
  const field =
    event && focus?.index === activeIndex && focus.path !== null
      ? shownPath(event, focus.path)
      : null;
  const mark = field !== null ? (printed.ranges.get(field) ?? null) : null;
  useEffect(() => {
    // Each "locate" scrolls once: replay or stepping back onto this event later
    // frames the field again but leaves the page where the learner put it.
    if (!focus?.reveal || !mark || revealed.current === focus) return;
    revealed.current = focus;
    markRef.current?.scrollIntoView({
      block: "center",
      behavior: reducedMotion ? "auto" : "smooth",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, mark?.from]);
  return (
    <div className="event-detail" data-testid="lab-event-detail">
      <div className="subpane-label">
        <span>{event ? label(event) : t("title")}</span>
        {event && (
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("copy")}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(
                  JSON.stringify(body, null, 2),
                );
                onCopied();
              } catch {
                s.setError(t("copyFailed"));
              }
            }}
          >
            {copied ? <Check size={15} /> : <Copy size={15} />}
          </Button>
        )}
      </div>
      {event ? (
        <div className="event-detail-body" key={activeIndex}>
          <p className="event-explanation">
            {isStreamDelta(event)
              ? t("streamDelta")
              : streamFacts(event)
                ? t("streamAssembled", {
                    count: streamFacts(event)!.chunkCount,
                  })
                : event.type.startsWith("approval_")
                  ? t("approval")
                  : event.type === "checkpoint"
                    ? t("checkpoint")
                    : event.data.representation === "sdk_standardized"
                      ? t("sdk")
                      : embedding
                        ? t("embeddingHttp")
                        : isExchange(event)
                          ? t("http")
                          : t("generic")}
          </p>
          {(isStreamDelta(event) || streamFacts(event)) && (
            <p className="event-explanation">
              {event.representation === "sdk_standardized" ||
              event.data.representation === "sdk_standardized"
                ? t("streamSdk")
                : t("streamHttp")}
            </p>
          )}
          <ResumeFromCheckpoint studio={s} event={event} />
          {shortened.truncated && (
            <p
              className="event-explanation"
              data-testid="lab-embedding-truncated"
            >
              {!showFull && (
                <span>
                  {t("embeddingTruncated", { count: SHOWN_VECTOR_NUMBERS })}
                </span>
              )}
              <Button
                variant="ghost"
                size="sm"
                aria-pressed={showFull}
                onClick={() => setFullIndex(showFull ? null : activeIndex)}
              >
                {showFull ? t("embeddingShowShort") : t("embeddingShowFull")}
              </Button>
            </p>
          )}
          <Code content={printed.text} mark={mark} markRef={markRef} />
        </div>
      ) : (
        <EmptyDetail active={active} />
      )}
    </div>
  );
}
