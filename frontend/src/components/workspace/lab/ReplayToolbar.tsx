import { useTranslation } from "react-i18next";
import { Download, Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import type { StudioState } from "../../../hooks/useStudio";
import { segmentColors } from "../../lab/controlColors";
import RubberSegment from "../../react-bits/RubberSegment";
import WakeSlider from "../../react-bits/WakeSlider";
import { Button } from "../../ui/button";

const PACINGS = ["uniform", "real1", "real2"] as const;
type Pacing = (typeof PACINGS)[number];

/**
 * Replay controls over the recorded events only: play / pause, step, rewind,
 * scrub, pacing and download. Disabled while a run is live.
 */
export function ReplayToolbar({ studio: s }: { studio: StudioState }) {
  const { t } = useTranslation("stage", { keyPrefix: "replay" });
  const { t: tb } = useTranslation("lab", { keyPrefix: "bench.replay" });
  const pacing: Pacing =
    s.replayOptions.pacing === "uniform"
      ? "uniform"
      : s.replayOptions.speed === 2
        ? "real2"
        : "real1";
  return (
    <div className="replay-toolbar" data-testid="lab-replay-toolbar">
      <Button
        variant="ghost"
        size="icon"
        disabled={s.running}
        data-testid="lab-replay-play"
        aria-label={s.playing ? tb("pause") : tb("play")}
        onClick={s.replay}
      >
        {s.playing ? <Pause size={15} /> : <Play size={15} />}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        disabled={s.running || s.cursor >= s.events.length}
        data-testid="lab-replay-step"
        aria-label={tb("step")}
        onClick={s.step}
      >
        <SkipForward size={15} />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        disabled={s.running}
        data-testid="lab-replay-rewind"
        aria-label={tb("rewind")}
        onClick={() => s.seek(0)}
      >
        <RotateCcw size={15} />
      </Button>
      <WakeSlider
        ariaLabel={tb("progress")}
        className="replay-slider"
        value={s.cursor}
        min={0}
        max={s.events.length}
        step={1}
        disabled={s.running}
        onChange={s.seek}
        height={24}
        restHeight={4}
        gap={3}
        fillColor="var(--accent)"
        trackColor="var(--line)"
      />
      <span>
        {s.cursor}/{s.events.length}
      </span>
      <RubberSegment
        aria-label={t("pacing")}
        size="sm"
        items={PACINGS.map((value) => ({ value, label: t(value) }))}
        value={pacing}
        disabled={s.running}
        onChange={(value) =>
          s.setReplayOptions(
            value === "uniform"
              ? { pacing: "uniform", speed: 1 }
              : { pacing: "realtime", speed: value === "real2" ? 2 : 1 },
          )
        }
        {...segmentColors}
      />
      <Button
        variant="ghost"
        size="icon"
        data-testid="lab-download-trace"
        aria-label={tb("download")}
        onClick={s.download}
      >
        <Download size={16} />
      </Button>
    </div>
  );
}
