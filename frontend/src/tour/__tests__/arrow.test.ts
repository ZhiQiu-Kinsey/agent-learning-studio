import { describe, expect, it } from "vitest";
import { arrowShape } from "../arrow";

/** The vertex that is not on the box edge touching the card: the tip. */
const tip = (points: string) =>
  points.split(" ").map((pair) => pair.split(",").map(Number));

describe("arrowShape", () => {
  it("sizes the box like Joyride: base × size above or below, size × base beside", () => {
    expect(arrowShape("top", 22, 10)).toMatchObject({ width: 22, height: 10 });
    expect(arrowShape("bottom-start", 22, 10)).toMatchObject({
      width: 22,
      height: 10,
    });
    expect(arrowShape("left", 22, 10)).toMatchObject({ width: 10, height: 22 });
    expect(arrowShape("right-end", 22, 10)).toMatchObject({
      width: 10,
      height: 22,
    });
  });

  it("points the tip away from the card, toward the framed element", () => {
    // Card above the target (placement top): the tip is at the bottom edge.
    expect(tip(arrowShape("top", 22, 10)!.points)).toContainEqual([11, 10]);
    // Card below: tip at the top edge. Card on the left: tip at the right edge.
    expect(tip(arrowShape("bottom", 22, 10)!.points)).toContainEqual([11, 0]);
    expect(tip(arrowShape("left", 22, 10)!.points)).toContainEqual([10, 11]);
    expect(tip(arrowShape("right", 22, 10)!.points)).toContainEqual([0, 11]);
  });

  it("draws nothing for a centred card", () => {
    expect(arrowShape("center", 22, 10)).toBeNull();
  });
});
