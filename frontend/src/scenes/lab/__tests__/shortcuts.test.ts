import { describe, expect, it } from "vitest";
import {
  cyclePacing,
  isLabShortcutTarget,
  jumpByTime,
  resolveLabShortcut,
  type ShortcutKeyEvent,
} from "../shortcuts";

/** Fake element: `closest` matches when any listed selector part appears in the query. */
function element(matching: string[] = [], isContentEditable = false) {
  return {
    isContentEditable,
    closest: (selector: string) =>
      selector
        .split(",")
        .map((part) => part.trim())
        .some((part) => matching.includes(part))
        ? {}
        : null,
  };
}

const key = (
  value: string,
  extra: Partial<ShortcutKeyEvent> = {},
): ShortcutKeyEvent => ({
  key: value,
  shiftKey: false,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  target: element(),
  ...extra,
});

describe("isLabShortcutTarget", () => {
  it("accepts the window, the page and plain elements", () => {
    expect(isLabShortcutTarget(null, " ")).toBe(true);
    expect(isLabShortcutTarget({}, "ArrowLeft")).toBe(true);
    expect(isLabShortcutTarget(element(), "?")).toBe(true);
  });

  it.each([
    "input",
    "textarea",
    "select",
    "[contenteditable]:not([contenteditable='false'])",
    "[role='slider']",
    "[role='combobox']",
    "[role='listbox']",
    "[role='dialog']",
  ])("rejects every key inside %s", (selector) => {
    for (const value of [" ", "ArrowLeft", "]", "?"])
      expect(isLabShortcutTarget(element([selector]), value)).toBe(false);
  });

  it("rejects editable hosts reported by isContentEditable", () => {
    expect(isLabShortcutTarget(element([], true), " ")).toBe(false);
  });

  it("leaves Space to buttons and links, but arrows still step from a button", () => {
    const button = element(["button"]);
    expect(isLabShortcutTarget(button, " ")).toBe(false);
    expect(isLabShortcutTarget(button, "ArrowRight")).toBe(true);
    expect(isLabShortcutTarget(element(["a[href]"]), " ")).toBe(false);
  });

  it("leaves arrows to tabs and radio groups", () => {
    expect(isLabShortcutTarget(element(["[role='tab']"]), "ArrowLeft")).toBe(
      false,
    );
    expect(
      isLabShortcutTarget(element(["[role='radiogroup']"]), "ArrowRight"),
    ).toBe(false);
    expect(isLabShortcutTarget(element(["[role='radiogroup']"]), "]")).toBe(
      true,
    );
  });
});

describe("resolveLabShortcut", () => {
  it("maps every documented key", () => {
    expect(resolveLabShortcut(key(" "))).toBe("toggle-play");
    expect(resolveLabShortcut(key("ArrowLeft"))).toBe("step-back");
    expect(resolveLabShortcut(key("ArrowRight"))).toBe("step-forward");
    expect(resolveLabShortcut(key("ArrowLeft", { shiftKey: true }))).toBe(
      "jump-back",
    );
    expect(resolveLabShortcut(key("ArrowRight", { shiftKey: true }))).toBe(
      "jump-forward",
    );
    expect(resolveLabShortcut(key("["))).toBe("slower");
    expect(resolveLabShortcut(key("]"))).toBe("faster");
    expect(resolveLabShortcut(key("?", { shiftKey: true }))).toBe("help");
    expect(resolveLabShortcut(key("a"))).toBeNull();
  });

  it("ignores Ctrl, ⌘ and Alt combinations", () => {
    for (const modifier of ["ctrlKey", "metaKey", "altKey"] as const) {
      expect(resolveLabShortcut(key(" ", { [modifier]: true }))).toBeNull();
      expect(
        resolveLabShortcut(key("ArrowRight", { [modifier]: true })),
      ).toBeNull();
    }
  });

  it("ignores typing, IME composition and already handled keys", () => {
    expect(
      resolveLabShortcut(key(" ", { target: element(["textarea"]) })),
    ).toBeNull();
    expect(resolveLabShortcut(key("]", { isComposing: true }))).toBeNull();
    expect(resolveLabShortcut(key(" ", { defaultPrevented: true }))).toBeNull();
  });
});

describe("jumpByTime", () => {
  const at = (ms: number) => new Date(Date.UTC(2026, 0, 1) + ms).toISOString();
  // Events at 0, 0.2, 0.4, 1.5, 1.6, 4.0 s.
  const timestamps = [0, 200, 400, 1500, 1600, 4000].map(at);

  it("moves forward to the last event within about one second", () => {
    expect(jumpByTime(timestamps, 1, 1)).toBe(3);
    expect(jumpByTime(timestamps, 0, 1)).toBe(3);
  });

  it("moves at least one event across a long gap", () => {
    // From 0.4 s nothing else happens before 1.4 s; still advance to 1.5 s.
    expect(jumpByTime(timestamps, 3, 1)).toBe(4);
    expect(jumpByTime(timestamps, 5, 1)).toBe(6);
    expect(jumpByTime(timestamps, 6, -1)).toBe(5);
  });

  it("moves backward until the shown event is a second earlier", () => {
    expect(jumpByTime(timestamps, 5, -1)).toBe(3);
    expect(jumpByTime(timestamps, 3, -1)).toBe(0);
  });

  it("clamps at both ends", () => {
    expect(jumpByTime(timestamps, 6, 1)).toBe(6);
    expect(jumpByTime(timestamps, 0, -1)).toBe(0);
    expect(jumpByTime(timestamps, 99, 1)).toBe(6);
    expect(jumpByTime([], 0, 1)).toBe(0);
  });

  it("falls back to a single step when timestamps are unreadable", () => {
    const broken = ["x", "y", "z"];
    expect(jumpByTime(broken, 1, 1)).toBe(2);
    expect(jumpByTime(broken, 2, -1)).toBe(1);
  });
});

describe("cyclePacing", () => {
  const uniform = { pacing: "uniform", speed: 1 } as const;
  const real1 = { pacing: "realtime", speed: 1 } as const;
  const real2 = { pacing: "realtime", speed: 2 } as const;

  it("] goes uniform → 1× → 2× and wraps", () => {
    expect(cyclePacing(uniform, 1)).toEqual(real1);
    expect(cyclePacing(real1, 1)).toEqual(real2);
    expect(cyclePacing(real2, 1)).toEqual(uniform);
  });

  it("[ goes the other way and wraps", () => {
    expect(cyclePacing(real2, -1)).toEqual(real1);
    expect(cyclePacing(real1, -1)).toEqual(uniform);
    expect(cyclePacing(uniform, -1)).toEqual(real2);
  });

  it("treats uniform pacing at any speed as the uniform preset", () => {
    expect(cyclePacing({ pacing: "uniform", speed: 2 }, 1)).toEqual(real1);
  });
});
