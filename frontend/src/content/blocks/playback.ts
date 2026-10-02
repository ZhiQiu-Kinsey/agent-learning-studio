/**
 * Playback state for a teaching illustration. Nothing starts by itself: the
 * initial state is paused on the first step, and only `toggle` (a click on the
 * play button) starts the clock. Any manual move pauses; reaching the last
 * step stops, and the next toggle replays from the first step.
 */
export interface Playback {
  cursor: number;
  playing: boolean;
}

export type PlaybackAction =
  | { type: "toggle" }
  | { type: "tick" }
  | { type: "seek"; cursor: number }
  | { type: "pause" };

/** Time each step stays on screen while playing. */
export const PLAYBACK_INTERVAL_MS = 1300;

export const initialPlayback: Playback = { cursor: 1, playing: false };

const clamp = (cursor: number, total: number) =>
  Math.min(Math.max(1, Math.round(cursor)), Math.max(1, total));

export function playbackReducer(
  state: Playback,
  action: PlaybackAction,
  total: number,
): Playback {
  switch (action.type) {
    case "toggle":
      if (state.playing) return { ...state, playing: false };
      // At the end the play button reads "replay": start over and play.
      return state.cursor >= total
        ? { cursor: 1, playing: total > 1 }
        : { ...state, playing: true };
    case "tick": {
      if (!state.playing) return state;
      const cursor = clamp(state.cursor + 1, total);
      return { cursor, playing: cursor < total };
    }
    case "seek":
      return { cursor: clamp(action.cursor, total), playing: false };
    case "pause":
      return state.playing ? { ...state, playing: false } : state;
  }
}
