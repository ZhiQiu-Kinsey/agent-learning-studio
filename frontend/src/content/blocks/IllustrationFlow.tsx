import { useEffect, useMemo, useReducer, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import {
  ChevronLeft,
  ChevronRight,
  Pause,
  Play,
  RotateCcw,
} from "lucide-react";
import { Button } from "../../components/ui/button";
import { AgentStage } from "../../stage/AgentStage";
import type { Trace } from "../../types";
import type { Flow, Illustration } from "../types.gen";
import {
  initialPlayback,
  PLAYBACK_INTERVAL_MS,
  playbackReducer,
  type PlaybackAction,
} from "./playback";

/**
 * A teaching illustration rendered by the same stage as real runs. Every event
 * carries provenance=illustration, so the stage draws it dashed with the
 * "not a run record" watermark. The learner steps it by hand or presses play;
 * nothing starts on its own. Playing advances on a fixed clock, stops on the
 * last step (the button then replays), and any manual move pauses. Static
 * motion still plays; the stage just skips its transitions between steps.
 */
export function IllustrationFlow({
  block,
  illustration,
}: {
  block: Flow;
  illustration: Illustration;
}) {
  const { t } = useTranslation("blocks", { keyPrefix: "flow" });
  const events = useMemo<Trace[]>(
    () =>
      illustration.events.map((event) => ({
        type: event.type,
        round: event.round ?? null,
        timestamp: "",
        data: event.data,
        provenance: "illustration",
      })),
    [illustration],
  );
  const total = events.length;
  const [{ cursor, playing }, dispatch] = useReducer(
    (state: typeof initialPlayback, action: PlaybackAction) =>
      playbackReducer(state, action, total),
    initialPlayback,
  );
  const ended = cursor >= total;

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(
      () => dispatch({ type: "tick" }),
      PLAYBACK_INTERVAL_MS,
    );
    return () => window.clearTimeout(timer);
  }, [playing, cursor]);
  // A hidden tab pauses instead of racing through steps nobody sees.
  useEffect(() => {
    if (!playing) return;
    const onHidden = () => {
      if (document.hidden) dispatch({ type: "pause" });
    };
    document.addEventListener("visibilitychange", onHidden);
    return () => document.removeEventListener("visibilitychange", onHidden);
  }, [playing]);

  const position = t("position", { current: cursor, total });
  const share = total > 1 ? (cursor - 1) / (total - 1) : 1;
  return (
    <section
      className="illustration-flow"
      aria-label={block.title ?? t("region")}
      data-testid="illustration-flow"
    >
      {block.title && <h3>{block.title}</h3>}
      <AgentStage events={events} cursor={cursor} live={false} />
      <div
        className="illustration-controls"
        data-playing={playing || undefined}
        style={
          {
            "--flow-share": share,
            "--flow-interval": `${PLAYBACK_INTERVAL_MS}ms`,
          } as CSSProperties
        }
      >
        <Button
          size="sm"
          variant="ghost"
          className="illustration-back"
          disabled={cursor <= 1}
          onClick={() => dispatch({ type: "seek", cursor: cursor - 1 })}
        >
          <ChevronLeft aria-hidden="true" />
          {t("back")}
        </Button>
        {/* One element across states so focus survives the switch to replay. */}
        <Button
          size="sm"
          variant="outline"
          className="illustration-play"
          aria-label={ended ? t("replay") : t("play")}
          aria-pressed={ended ? undefined : playing}
          title={ended ? undefined : playing ? t("pauseHint") : t("playHint")}
          disabled={total <= 1}
          data-testid="illustration-play"
          onClick={() => dispatch({ type: "toggle" })}
        >
          {ended ? (
            <RotateCcw aria-hidden="true" />
          ) : playing ? (
            <Pause aria-hidden="true" />
          ) : (
            <Play aria-hidden="true" />
          )}
          <span>{ended ? t("replay") : t("play")}</span>
          {playing && (
            <i
              key={cursor}
              className="illustration-play-clock"
              aria-hidden="true"
            />
          )}
        </Button>
        <label className="illustration-scrub">
          <span className="sr-only">{t("scrub")}</span>
          <input
            type="range"
            min={1}
            max={Math.max(1, total)}
            step={1}
            value={cursor}
            aria-valuetext={position}
            disabled={total <= 1}
            onChange={(event) =>
              dispatch({ type: "seek", cursor: Number(event.target.value) })
            }
          />
        </label>
        <span className="illustration-position">{position}</span>
        <Button
          size="sm"
          className="illustration-next"
          disabled={ended}
          onClick={() => dispatch({ type: "seek", cursor: cursor + 1 })}
        >
          {t("step")}
          <ChevronRight aria-hidden="true" />
        </Button>
      </div>
      {block.caption && <p className="illustration-caption">{block.caption}</p>}
    </section>
  );
}
