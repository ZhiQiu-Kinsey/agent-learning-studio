import { useTranslation } from "react-i18next";
import type { StudioState } from "../../../hooks/useStudio";
import { LessonExtension } from "../../../lesson-extensions/LessonExtension";
import { AgentStage } from "../../../stage/AgentStage";
import { ContextFilm } from "../../../stage/ContextFilm";
import { Lenses } from "../../../stage/Lenses";
import { Timeline } from "../../../stage/Timeline";
import { ToolCards } from "../../../stage/ToolCards";
import { EventDetail } from "./EventDetail";
import { EventList } from "./EventList";
import { ReplayToolbar } from "./ReplayToolbar";
import { RunActivity } from "./RunActivity";
import { RunMetrics } from "./RunMetrics";
import { ToolCallChips } from "./ToolCallChips";
import type { RunView } from "./useRunView";

/**
 * The "execution record" tab: stage, metrics, live activity, tool-call chips,
 * replay controls, timeline, then the event list beside the event inspector
 * (where observe points and the guide point), then film and cards and lenses.
 * Rendered as siblings so the tab's layout rules apply.
 */
export function RunObservatory({
  studio: s,
  run,
  active,
  spotlight,
  copied,
  onCopied,
}: {
  studio: StudioState;
  run: RunView;
  active: boolean;
  spotlight?: string | null;
  copied: boolean;
  onCopied: () => void;
}) {
  const { t } = useTranslation("stage", { keyPrefix: "replay" });
  const { t: tb } = useTranslation("lab", { keyPrefix: "bench.replay" });
  const activeIndex = s.active ? s.visible.indexOf(s.active) : -1;
  return (
    <>
      <LessonExtension
        slot="inspector"
        extensionKey={s.detail?.ui?.inspector}
        studio={s}
        active={active}
      >
        <AgentStage
          events={s.events}
          cursor={s.cursor}
          live={run.live}
          spotlight={spotlight}
        />
      </LessonExtension>
      <RunMetrics visible={s.visible} cursor={s.cursor} />
      {s.running && <RunActivity openLlm={run.openLlm} last={run.last} />}
      <ToolCallChips
        spans={run.stage.spans}
        events={s.events}
        live={run.live}
        activeIndex={activeIndex}
        onSelect={s.selectEvent}
      />
      {s.events.length > 0 && <ReplayToolbar studio={s} />}
      {s.events.length > 1 && (
        <Timeline
          events={s.events}
          spans={run.finalSpans}
          cursor={s.cursor}
          onSeek={s.seek}
        />
      )}
      {s.replayGap?.compressed && (
        <p className="replay-footnote" role="status">
          {t("compressed")}
        </p>
      )}
      <div className="trace-split">
        <EventList studio={s} />
        <EventDetail
          studio={s}
          active={active}
          copied={copied}
          onCopied={onCopied}
        />
      </div>
      {s.events.length > 0 && (
        <div className="stage-detail-grid">
          <ContextFilm film={run.stage.film} onSelect={s.selectEvent} />
          <ToolCards
            spans={run.stage.spans}
            events={s.events}
            live={s.running}
            onSelect={s.selectEvent}
          />
        </div>
      )}
      <Lenses visible={s.visible} film={run.stage.film} />
      <p className="replay-footnote">{tb("footnote")}</p>
    </>
  );
}
