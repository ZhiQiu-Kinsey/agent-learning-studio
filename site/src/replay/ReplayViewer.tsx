import { lazy, Suspense, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AgentStage } from "@studio/stage/AgentStage";
import { ContextFilm } from "@studio/stage/ContextFilm";
import { Lenses } from "@studio/stage/Lenses";
import { Timeline } from "@studio/stage/Timeline";
import { ToolCards } from "@studio/stage/ToolCards";
import { useStageProjection } from "@studio/stage/useStageProjection";
import { ApprovalPanel } from "@studio/components/workspace/lab/ApprovalPanel";
import { EventDetail } from "@studio/components/workspace/lab/EventDetail";
import { EventList } from "@studio/components/workspace/lab/EventList";
import { ReplayToolbar } from "@studio/components/workspace/lab/ReplayToolbar";
import { RunMetrics } from "@studio/components/workspace/lab/RunMetrics";
import { ToolCallChips } from "@studio/components/workspace/lab/ToolCallChips";
import type { Trace } from "@studio/types";
import type { RecordingEntry } from "../data/types";
import { loadRecording } from "./loadRecording";
import { asStudio, useRecordingPlayer } from "./useRecordingPlayer";

// The lesson's own inspector view, as the platform shows it; only trusted build-time imports.
const inspectors: Record<string, ReturnType<typeof lazy<typeof import("@studio/lesson-extensions/shared/EvidenceBoard").default>>> = {
  "evidence-board": lazy(() => import("@studio/lesson-extensions/shared/EvidenceBoard")),
};

/** Same format as the platform's recording view (scenes/lab/RecordingView.tsx). */
const formatRecordingDate = (recordedAt: string, language: string) =>
  new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(
    new Date(recordedAt),
  );

type Loaded =
  | { state: "loading" }
  | { state: "failed"; reason: string }
  | { state: "ready"; events: Trace[] };

/** Loads one published recording and replays it read-only with the platform's views. */
export function ReplayViewer({
  entry,
  inspector,
}: {
  entry: RecordingEntry;
  inspector: string | null;
}) {
  const { t } = useTranslation("site", { keyPrefix: "replays" });
  const [loaded, setLoaded] = useState<Loaded>({ state: "loading" });
  useEffect(() => {
    const abort = new AbortController();
    setLoaded({ state: "loading" });
    loadRecording(entry.path, { signal: abort.signal })
      .then((events) => {
        if (!abort.signal.aborted) setLoaded({ state: "ready", events });
      })
      .catch((reason: unknown) => {
        if (!abort.signal.aborted)
          setLoaded({
            state: "failed",
            reason: reason instanceof Error ? reason.message : String(reason),
          });
      });
    return () => abort.abort();
  }, [entry.path]);
  if (loaded.state === "loading")
    return (
      <p className="replay-status" role="status">
        {t("loading")}
      </p>
    );
  if (loaded.state === "failed")
    return (
      <p className="replay-status" role="alert">
        {t("failed", { reason: loaded.reason })}
      </p>
    );
  return (
    <LoadedReplay
      key={entry.path}
      entry={entry}
      events={loaded.events}
      inspector={inspector}
    />
  );
}

function LoadedReplay({
  entry,
  events,
  inspector,
}: {
  entry: RecordingEntry;
  events: Trace[];
  inspector: string | null;
}) {
  const { t, i18n } = useTranslation("site", { keyPrefix: "replays" });
  const { t: ts } = useTranslation("stage", { keyPrefix: "replay" });
  const [copied, setCopied] = useState(false);
  const player = useRecordingPlayer(events, {
    lessonId: entry.lesson,
    runId: entry.metadata.run_id,
    locale: entry.metadata.locale,
    fileName: `${import.meta.env.BASE_URL}${entry.path}`,
  });
  const studio = asStudio(player);
  const { stage, final } = useStageProjection(events, player.cursor);
  const activeIndex = player.active ? player.visible.indexOf(player.active) : -1;
  const answer = player.visible.findLast((event) => event.type === "answer");
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(timer);
  }, [copied]);
  const Inspector = inspector ? inspectors[inspector] : undefined;
  return (
    <div className="replay-viewer inspector-trace" data-testid="replay-viewer">
      <AgentStage
        events={events}
        cursor={player.cursor}
        live={false}
        recording={{
          model: entry.metadata.model,
          date: formatRecordingDate(entry.metadata.recorded_at, i18n.language),
        }}
      />
      <ReplayToolbar studio={studio} />
      {events.length > 1 && (
        <Timeline
          events={events}
          spans={final.spans}
          cursor={player.cursor}
          onSeek={player.seek}
        />
      )}
      {player.replayGap?.compressed && (
        <p className="replay-footnote" role="status">
          {ts("compressed")}
        </p>
      )}
      <section className="replay-answer" aria-label={t("answer")}>
        <h4>{t("answer")}</h4>
        {answer ? (
          <p lang={entry.metadata.locale} data-testid="replay-answer">
            {String(answer.data.content ?? "")}
          </p>
        ) : (
          <p className="replay-muted">{t("answerPending")}</p>
        )}
      </section>
      <details className="replay-more" data-testid="replay-more">
        <summary>{t("more")}</summary>
        <div className="replay-more-body">
          <ApprovalPanel studio={studio} live={false} />
          <RunMetrics visible={player.visible} cursor={player.cursor} />
          <ToolCallChips
            spans={stage.spans}
            events={events}
            live={false}
            activeIndex={activeIndex}
            onSelect={player.selectEvent}
          />
          <div className="trace-split">
            <EventList studio={studio} />
            <EventDetail
              studio={studio}
              active={false}
              copied={copied}
              onCopied={() => setCopied(true)}
            />
          </div>
          {Inspector && (
            <Suspense fallback={null}>
              <Inspector studio={studio} active>
                {null}
              </Inspector>
            </Suspense>
          )}
          <div className="stage-detail-grid">
            <ContextFilm film={stage.film} onSelect={player.selectEvent} />
            <ToolCards
              spans={stage.spans}
              events={events}
              live={false}
              onSelect={player.selectEvent}
            />
          </div>
          <Lenses visible={player.visible} film={stage.film} />
        </div>
      </details>
    </div>
  );
}
