import { describe, expect, it } from "vitest";
import { skipTarget } from "../skip";

describe("skipTarget", () => {
  it("skips a missing step in the direction of travel", () => {
    expect(skipTarget(2, 1, 5)).toBe(3);
    expect(skipTarget(2, -1, 5)).toBe(1);
  });

  it("ends the tour past the last step", () => {
    expect(skipTarget(4, 1, 5)).toBeNull();
  });

  it("turns forward when the first step is missing on the way back", () => {
    expect(skipTarget(0, -1, 5)).toBe(1);
    expect(skipTarget(0, -1, 1)).toBeNull();
  });
});
