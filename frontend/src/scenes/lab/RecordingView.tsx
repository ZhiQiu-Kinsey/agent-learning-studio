import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { jsonFetch } from "../../api";
import type { Trace } from "../../types";
import { AgentStage } from "../../stage/AgentStage";
import { Timeline } from "../../stage/Timeline";
import { ToolCards } from "../../stage/ToolCards";
import { ContextFilm } from "../../stage/ContextFilm";
import { useStageProjection } from "../../stage/useStageProjection";
import { RuntimeLanguageNote } from "../../components/workspace/lab/RunLanguage";

export interface RecordingMeta {
  name: string;
  valid: boolean;
  error_code: string | null;
  metadata: {
    model: string;
    recorded_at: string;
    provider_label?: string;
    /** The run language of the recorded run. */
    locale?: string;
  } | null;
}

/** Recording date as shown in the source switch and on the stage badge. */
export const formatRecordingDate = (recordedAt: string, language: string) =>
  new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(
    new Date(recordedAt),
  );

const NO_EVENTS: Trace[] = [];

/**
 * Read-only view of a recording shipped with the lesson. It never mixes into
 * the learner's runs or progress; the stage labels it "录制的真实运行 · 模型 · 日期".
 */
export function RecordingView({
  lessonId,
  recording,
}: {
  lessonId: string;
  recording: RecordingMeta;
}) {
  const { t, i18n } = useTranslation("lesson", { keyPrefix: "lab.recording" });
  const [events, setEvents] = useState<Trace[] | null>(null);
  const [error, setError] = useState("");
  const [cursor, setCursor] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    setEvents(null);
    setError("");
    jsonFetch<{ events: Trace[] }>(
      `/api/lessons/${encodeURIComponent(lessonId)}/recordings/${encodeURIComponent(recording.name)}`,
      { signal: abort.signal },
    )
      .then((value) => {
        if (abort.signal.aborted) return;
        setEvents(value.events);
        setCursor(value.events.length);
      })
      .catch((reason: unknown) => {
        if (!abort.signal.aborted)
          setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => abort.abort();
  }, [lessonId, recording.name]);
  const { stage, final } = useStageProjection(events ?? NO_EVENTS, cursor);
  if (error) return <p role="alert">{t("failed", { reason: error })}</p>;
  if (!events) return <p role="status">{t("loading")}</p>;
  const date = recording.metadata
    ? formatRecordingDate(recording.metadata.recorded_at, i18n.language)
    : "";
  return (
    <div className="recording-view" data-testid="recording-view">
      <RuntimeLanguageNote
        locale={recording.metadata?.locale}
        kind="run"
        testId="recording-locale"
      />
      <AgentStage
        events={events}
        cursor={cursor}
        live={false}
        recording={{ model: recording.metadata?.model ?? "", date }}
      />
      <input
        type="range"
        className="recording-slider"
        min={0}
        max={events.length}
        value={cursor}
        aria-valuetext={t("position", { cursor, total: events.length })}
        onChange={(event) => setCursor(Number(event.target.value))}
      />
      <Timeline
        events={events}
        spans={final.spans}
        cursor={cursor}
        onSeek={setCursor}
      />
      <div className="stage-detail-grid">
        <ContextFilm film={stage.film} />
        <ToolCards spans={stage.spans} events={events} live={false} />
      </div>
    </div>
  );
}
