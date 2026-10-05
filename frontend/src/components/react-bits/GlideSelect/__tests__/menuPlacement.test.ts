import { describe, expect, it } from "vitest";
import { MENU_GAP, menuPlacement } from "../utils";

describe("menuPlacement", () => {
  it("keeps the preferred side when the whole menu fits", () => {
    expect(
      menuPlacement(
        { top: 100, bottom: 140 },
        { top: 0, bottom: 800 },
        300,
        "bottom",
      ),
    ).toEqual({ side: "bottom", maxHeight: null });
  });

  it("measures room inside a clipping dialog, not the window", () => {
    // The settings dialog ends at 600 although the window is 1080 tall:
    // 300px do not fit below the trigger, but they do above it.
    expect(
      menuPlacement(
        { top: 400, bottom: 440 },
        { top: 40, bottom: 600 },
        300,
        "bottom",
      ),
    ).toEqual({ side: "top", maxHeight: null });
  });

  it("caps the height on the roomier side when neither side fits", () => {
    const fit = menuPlacement(
      { top: 200, bottom: 240 },
      { top: 100, bottom: 500 },
      340,
      "bottom",
    );
    expect(fit).toEqual({ side: "bottom", maxHeight: 500 - 240 - MENU_GAP });
    // The capped menu stays inside the visible area.
    expect(240 + MENU_GAP + fit.maxHeight!).toBeLessThanOrEqual(500);
  });

  it("never caps below the minimum height", () => {
    expect(
      menuPlacement(
        { top: 20, bottom: 60 },
        { top: 0, bottom: 80 },
        300,
        "bottom",
        48,
      ),
    ).toEqual({ side: "bottom", maxHeight: 48 });
  });
});
