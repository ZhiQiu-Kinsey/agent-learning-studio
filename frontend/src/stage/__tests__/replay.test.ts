import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createReplayClock,
  gapBefore,
  MAX_REAL_GAP_MS,
  UNIFORM_STEP_MS,
  type ReplayState,
} from "../replay";

const stamps = [
  "2026-10-02T00:00:00.000Z",
  "2026-10-02T00:00:00.400Z", // +400ms
  "2026-10-02T00:00:10.400Z", // +10s (long model wait)
  "2026-10-02T00:00:10.500Z", // +100ms
];

describe("gapBefore", () => {
  it("uses uniform steps or real server gaps, halved at 2×", () => {
    expect(gapBefore(stamps, 1, { pacing: "uniform", speed: 1 })).toEqual({
      delayMs: UNIFORM_STEP_MS,
      compressed: false,
    });
    expect(gapBefore(stamps, 1, { pacing: "realtime", speed: 1 })).toEqual({
      delayMs: 400,
      compressed: false,
    });
    expect(gapBefore(stamps, 1, { pacing: "realtime", speed: 2 })).toEqual({
      delayMs: 200,
      compressed: false,
    });
  });

  it("compresses long real gaps and says so", () => {
    expect(gapBefore(stamps, 2, { pacing: "realtime", speed: 1 })).toEqual({
      delayMs: MAX_REAL_GAP_MS,
      compressed: true,
    });
  });

  it("falls back to uniform pacing when timestamps are unreadable", () => {
    expect(
      gapBefore(["x", "y"], 1, { pacing: "realtime", speed: 1 }).delayMs,
    ).toBe(UNIFORM_STEP_MS);
  });
});

describe("replay clock", () => {
  let states: ReplayState[];
  beforeEach(() => {
    vi.useFakeTimers();
    states = [];
  });
  afterEach(() => vi.useRealTimers());
  const clock = (cursor = 0) =>
    createReplayClock(stamps, (state) => states.push(state), undefined, {
      cursor,
    });

  it("plays to the end at the chosen pacing and stops", () => {
    const replay = clock();
    replay.setOptions({ pacing: "realtime" });
    replay.play();
    expect(replay.get().cursor).toBe(0);
    vi.advanceTimersByTime(0);
    expect(replay.get().cursor).toBe(1);
    vi.advanceTimersByTime(399);
    expect(replay.get().cursor).toBe(1);
    vi.advanceTimersByTime(1);
    expect(replay.get().cursor).toBe(2);
    expect(replay.get().waiting).toEqual({
      delayMs: MAX_REAL_GAP_MS,
      compressed: true,
    });
    vi.advanceTimersByTime(MAX_REAL_GAP_MS + 100);
    expect(replay.get()).toMatchObject({
      cursor: 4,
      playing: false,
      waiting: null,
    });
  });

  it("drops timers scheduled before a seek, pause or speed change", () => {
    const replay = clock();
    replay.play();
    vi.advanceTimersByTime(0); // cursor 1, next step pending at 950ms
    replay.seek(3);
    vi.advanceTimersByTime(UNIFORM_STEP_MS - 1);
    expect(replay.get().cursor).toBe(3); // the old 950ms timer did not fire into the new position
    vi.advanceTimersByTime(1);
    expect(replay.get().cursor).toBe(4);

    const paused = clock();
    paused.play();
    vi.advanceTimersByTime(0);
    paused.pause();
    vi.advanceTimersByTime(10_000);
    expect(paused.get()).toMatchObject({ cursor: 1, playing: false });

    const faster = clock();
    faster.play();
    vi.advanceTimersByTime(0);
    faster.setOptions({ speed: 2 });
    vi.advanceTimersByTime(UNIFORM_STEP_MS / 2);
    expect(faster.get().cursor).toBe(2);
  });

  it("steps by hand, clamps to the run and restarts from the end", () => {
    const replay = clock(4);
    replay.step(-1);
    expect(replay.get()).toMatchObject({ cursor: 3, playing: false });
    replay.seek(-5);
    expect(replay.get().cursor).toBe(0);
    replay.seek(99);
    replay.play();
    expect(replay.get().cursor).toBe(0);
    replay.dispose();
    vi.advanceTimersByTime(10_000);
    expect(replay.get().cursor).toBe(0);
  });
});
