import { useEffect, useRef } from "react";
import type { StudioState } from "../../hooks/useStudio";
import {
  cyclePacing,
  jumpByTime,
  resolveLabShortcut,
  type LabShortcut,
} from "./shortcuts";

/**
 * Keyboard control of the learner's own replay. Only reads recorded events:
 * every action goes through the studio's seek / replay / pacing API.
 */
export function useLabShortcuts({
  studio,
  enabled,
  onHelp,
}: {
  studio: StudioState;
  /**
   * Lab scene visible, nothing running, the learner's own run on screen, and
   * no guide open (the guide owns the keyboard and the replay position).
   */
  enabled: boolean;
  onHelp: () => void;
}) {
  // Latest values without re-binding the listener on every cursor change.
  const latest = useRef({ studio, onHelp });
  latest.current = { studio, onHelp };

  useEffect(() => {
    if (!enabled) return;
    const onKey = (event: KeyboardEvent) => {
      const { studio: s, onHelp: help } = latest.current;
      const action = resolveLabShortcut(event);
      if (!action || s.running) return;
      if (action !== "help" && !s.events.length) return;
      event.preventDefault();
      run(action, s, help);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
}

function run(action: LabShortcut, s: StudioState, help: () => void) {
  const timestamps = () => s.events.map((event) => event.timestamp);
  switch (action) {
    case "toggle-play":
      s.replay();
      break;
    case "step-back":
      s.seek(s.cursor - 1);
      break;
    case "step-forward":
      s.step();
      break;
    case "jump-back":
      s.seek(jumpByTime(timestamps(), s.cursor, -1));
      break;
    case "jump-forward":
      s.seek(jumpByTime(timestamps(), s.cursor, 1));
      break;
    case "slower":
      s.setReplayOptions(cyclePacing(s.replayOptions, -1));
      break;
    case "faster":
      s.setReplayOptions(cyclePacing(s.replayOptions, 1));
      break;
    case "help":
      help();
      break;
  }
}
