/**
 * Replay clock. Steps a cursor through already-recorded events; it never sends
 * requests or runs tools. Pacing is either uniform or proportional to the real
 * gaps between server timestamps (1× / 2×). Every play/pause/seek/speed change
 * bumps a generation token, so a timer scheduled before the change can never
 * move the cursor afterwards.
 */
export type ReplayPacing = "uniform" | "realtime";

export interface ReplayOptions {
  pacing: ReplayPacing;
  speed: 1 | 2;
}

/** Long real gaps are shortened for watching; the UI labels them as compressed. */
export const UNIFORM_STEP_MS = 950;
export const MAX_REAL_GAP_MS = 3000;
export const MIN_REAL_GAP_MS = 60;

export interface Gap {
  delayMs: number;
  /** True when the real gap was longer than what replay waits. */
  compressed: boolean;
}

/** Delay before showing event `index` (index >= 1), from server timestamps only. */
export function gapBefore(
  timestamps: readonly string[],
  index: number,
  { pacing, speed }: ReplayOptions,
): Gap {
  if (pacing === "uniform")
    return { delayMs: UNIFORM_STEP_MS / speed, compressed: false };
  const real =
    Date.parse(timestamps[index]) - Date.parse(timestamps[index - 1]);
  if (!Number.isFinite(real) || real < 0)
    return { delayMs: UNIFORM_STEP_MS / speed, compressed: false };
  const scaled = real / speed;
  return {
    delayMs: Math.min(Math.max(scaled, MIN_REAL_GAP_MS), MAX_REAL_GAP_MS),
    compressed: scaled > MAX_REAL_GAP_MS,
  };
}

export interface ReplayState {
  cursor: number;
  playing: boolean;
  options: ReplayOptions;
  /** Gap currently being waited, for the "compressed" label. */
  waiting: Gap | null;
}

interface Timers {
  set: (callback: () => void, ms: number) => unknown;
  clear: (handle: unknown) => void;
}

export function createReplayClock(
  timestamps: readonly string[],
  onChange: (state: ReplayState) => void,
  timers: Timers = {
    set: (callback, ms) => setTimeout(callback, ms),
    clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
  },
  initial: Partial<ReplayState> = {},
) {
  const total = timestamps.length;
  let state: ReplayState = {
    cursor: Math.max(0, Math.min(initial.cursor ?? total, total)),
    playing: false,
    options: initial.options ?? { pacing: "uniform", speed: 1 },
    waiting: null,
  };
  let generation = 0;
  let handle: unknown = null;

  function emit(next: Partial<ReplayState>) {
    state = { ...state, ...next };
    onChange(state);
  }

  function stopTimer() {
    generation++;
    if (handle !== null) timers.clear(handle);
    handle = null;
  }

  function schedule() {
    const token = generation;
    if (state.cursor >= total) {
      emit({ playing: false, waiting: null });
      return;
    }
    const gap: Gap =
      state.cursor === 0
        ? { delayMs: 0, compressed: false }
        : gapBefore(timestamps, state.cursor, state.options);
    emit({ waiting: gap });
    handle = timers.set(() => {
      if (token !== generation) return; // stale timer from before a seek/pause/speed change
      handle = null;
      emit({ cursor: state.cursor + 1, waiting: null });
      schedule();
    }, gap.delayMs);
  }

  return {
    get: () => state,
    play() {
      stopTimer();
      // Playing from the end restarts from the beginning.
      emit({ playing: true, cursor: state.cursor >= total ? 0 : state.cursor });
      schedule();
    },
    pause() {
      stopTimer();
      emit({ playing: false, waiting: null });
    },
    seek(cursor: number) {
      const wasPlaying = state.playing;
      stopTimer();
      emit({ cursor: Math.max(0, Math.min(cursor, total)), waiting: null });
      if (wasPlaying) schedule();
    },
    step(delta: number) {
      this.pause();
      this.seek(state.cursor + delta);
    },
    setOptions(options: Partial<ReplayOptions>) {
      const wasPlaying = state.playing;
      stopTimer();
      emit({ options: { ...state.options, ...options }, waiting: null });
      if (wasPlaying) schedule();
    },
    dispose: stopTimer,
  };
}
