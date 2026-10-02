import { describe, expect, it } from "vitest";
import {
  initialPlayback,
  playbackReducer,
  type Playback,
  type PlaybackAction,
} from "../blocks/playback";

const run = (actions: PlaybackAction[], total = 4, from = initialPlayback) =>
  actions.reduce<Playback>(
    (state, action) => playbackReducer(state, action, total),
    from,
  );

describe("illustration playback", () => {
  it("starts paused and never advances without a click", () => {
    expect(initialPlayback).toEqual({ cursor: 1, playing: false });
    // A stray tick (no play pressed) changes nothing.
    expect(run([{ type: "tick" }, { type: "tick" }])).toEqual(initialPlayback);
  });

  it("plays step by step after toggle and stops on the last step", () => {
    const playing = run([{ type: "toggle" }]);
    expect(playing).toEqual({ cursor: 1, playing: true });
    expect(run([{ type: "tick" }], 4, playing)).toEqual({
      cursor: 2,
      playing: true,
    });
    expect(
      run([{ type: "tick" }, { type: "tick" }, { type: "tick" }], 4, playing),
    ).toEqual({ cursor: 4, playing: false });
    // Extra ticks after the end do nothing.
    expect(
      run(
        [
          { type: "tick" },
          { type: "tick" },
          { type: "tick" },
          { type: "tick" },
        ],
        4,
        playing,
      ),
    ).toEqual({ cursor: 4, playing: false });
  });

  it("replays from the first step when toggled at the end", () => {
    expect(run([{ type: "toggle" }], 4, { cursor: 4, playing: false })).toEqual(
      { cursor: 1, playing: true },
    );
  });

  it("pauses on manual steps and seeks, clamped to the range", () => {
    const playing = { cursor: 2, playing: true };
    expect(run([{ type: "seek", cursor: 3 }], 4, playing)).toEqual({
      cursor: 3,
      playing: false,
    });
    expect(run([{ type: "seek", cursor: 9 }], 4, playing).cursor).toBe(4);
    expect(run([{ type: "seek", cursor: 0 }], 4, playing).cursor).toBe(1);
    expect(run([{ type: "pause" }], 4, playing)).toEqual({
      cursor: 2,
      playing: false,
    });
    expect(run([{ type: "toggle" }], 4, playing)).toEqual({
      cursor: 2,
      playing: false,
    });
  });

  it("does not play a single-step illustration", () => {
    expect(run([{ type: "toggle" }], 1)).toEqual({ cursor: 1, playing: false });
  });
});
