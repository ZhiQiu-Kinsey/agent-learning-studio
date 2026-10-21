import { useEffect, useRef, useState } from "react";
import type { StudioState } from "@studio/hooks/useStudio";
import {
  createReplayClock,
  type Gap,
  type ReplayOptions,
} from "@studio/stage/replay";
import type { Trace } from "@studio/types";

/**
 * The part of the platform's StudioState that its replay views read. The site has
 * no backend: there is never a live run, an approval to decide or a run to resume.
 */
export type ReplayStudio = Pick<
  StudioState,
  | "events"
  | "visible"
  | "active"
  | "cursor"
  | "selectEvent"
  | "seek"
  | "replay"
  | "step"
  | "playing"
  | "replayOptions"
  | "setReplayOptions"
  | "replayGap"
  | "download"
  | "running"
  | "runId"
  | "runLocale"
  | "detached"
  | "stopping"
  | "restored"
  | "setError"
  | "decide"
  | "resume"
  | "lessonId"
>;

/**
 * The platform's views are typed against the whole StudioState; at runtime they read
 * only the fields above, and every live-run action is inert here.
 */
export const asStudio = (player: ReplayStudio) =>
  player as unknown as StudioState;

const refuse = () =>
  Promise.reject(new Error("A recording is read-only: nothing can be sent."));

/**
 * Replay state over one recording, with the same rules as useStudio's replay: the
 * cursor steps through recorded events only, on the shared replay clock
 * (stage/replay.ts), and nothing is ever requested or executed.
 */
export function useRecordingPlayer(
  events: readonly Trace[],
  { lessonId, runId, locale, fileName }: {
    lessonId: string;
    runId: string;
    locale: string | null;
    fileName: string;
  },
): ReplayStudio {
  const [cursor, setCursor] = useState(events.length);
  const [selected, setSelected] = useState(events.length - 1);
  const [playing, setPlaying] = useState(false);
  const [replayOptions, setReplayOptions] = useState<ReplayOptions>({
    pacing: "uniform",
    speed: 1,
  });
  const [replayGap, setReplayGap] = useState<Gap | null>(null);

  // A new recording opens at its end, like the platform's recording view.
  useEffect(() => {
    setPlaying(false);
    setCursor(events.length);
    setSelected(events.length - 1);
  }, [events]);

  const cursorRef = useRef(cursor);
  cursorRef.current = cursor;
  useEffect(() => {
    if (!playing) return;
    const clock = createReplayClock(
      events.map((event) => event.timestamp),
      (state) => {
        setCursor(state.cursor);
        setSelected(state.cursor - 1);
        setReplayGap(state.waiting);
        if (!state.playing) setPlaying(false);
      },
      undefined,
      { cursor: cursorRef.current, options: replayOptions },
    );
    clock.play();
    return () => {
      clock.dispose();
      setReplayGap(null);
    };
  }, [playing, events, replayOptions]);

  function seek(value: number) {
    if (!Number.isFinite(value)) return;
    const next = Math.max(0, Math.min(Math.round(value), events.length));
    setPlaying(false);
    setCursor(next);
    setSelected(next - 1);
  }
  function replay() {
    if (!events.length) return;
    if (cursor >= events.length) {
      setCursor(0);
      setSelected(-1);
    }
    setPlaying((value) => !value);
  }
  function download() {
    // The recording file exactly as published next to the site.
    const anchor = document.createElement("a");
    anchor.href = fileName;
    anchor.download = fileName.split("/").at(-1) ?? "recording.json";
    anchor.click();
  }
  const visible = events.slice(0, cursor);
  const active =
    selected >= 0 && selected < cursor ? (events[selected] ?? null) : null;
  return {
    events: events as Trace[],
    visible: visible as Trace[],
    active,
    cursor,
    selectEvent: (index: number) => {
      if (Number.isInteger(index) && index >= 0 && index < cursor)
        setSelected(index);
    },
    seek,
    replay,
    step: () => seek(cursor + 1),
    playing,
    replayOptions,
    setReplayOptions: (value) =>
      setReplayOptions((current) =>
        typeof value === "function" ? value(current) : value,
      ),
    replayGap,
    download,
    running: false,
    runId,
    runLocale: locale,
    detached: false,
    stopping: false,
    restored: null,
    setError: () => {},
    decide: refuse,
    resume: refuse,
    lessonId,
  };
}
