/**
 * Lab replay shortcuts as pure functions, so the guard and the seek math are
 * unit-tested without a DOM. The target guard follows the idea of OpenMAIC's
 * `isPresentationShortcutTarget` (never steal keys from fields, sliders,
 * menus or dialogs), reimplemented for this app's controls.
 */
import type { ReplayOptions } from "../../stage/replay";

export type LabShortcut =
  | "toggle-play"
  | "step-back"
  | "step-forward"
  | "jump-back"
  | "jump-forward"
  | "slower"
  | "faster"
  | "help";

/** Help overlay order; labels live in the `command` locale namespace. */
export const labShortcutList: readonly { id: LabShortcut; keys: string[] }[] = [
  { id: "toggle-play", keys: ["Space"] },
  { id: "step-back", keys: ["←"] },
  { id: "step-forward", keys: ["→"] },
  { id: "jump-back", keys: ["Shift", "←"] },
  { id: "jump-forward", keys: ["Shift", "→"] },
  { id: "slower", keys: ["["] },
  { id: "faster", keys: ["]"] },
  { id: "help", keys: ["?"] },
];

/** Structural subset of an element, so tests can pass plain objects. */
export interface ShortcutTarget {
  closest?: (selector: string) => unknown;
  isContentEditable?: boolean;
}

export interface ShortcutKeyEvent {
  key: string;
  shiftKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  target: unknown;
  isComposing?: boolean;
  defaultPrevented?: boolean;
}

/** Text entry and value controls own every key. */
const EDITING = [
  "input",
  "textarea",
  "select",
  "[contenteditable]:not([contenteditable='false'])",
  "[role='textbox']",
  "[role='searchbox']",
  "[role='combobox']",
  "[role='listbox']",
  "[role='slider']",
  "[role='spinbutton']",
].join(", ");
/** An open dialog or menu (command palette, help, settings) owns the keyboard. */
const OVERLAY = "[role='dialog'], [role='alertdialog'], [role='menu']";
/** Space already activates these natively; acting too would double-toggle. */
const SPACE_OWNERS = [
  "button",
  "a[href]",
  "summary",
  "[role='button']",
  "[role='link']",
  "[role='checkbox']",
  "[role='radio']",
  "[role='switch']",
  "[role='tab']",
  "[role='menuitem']",
  "[role='option']",
].join(", ");
/** Arrow keys move focus or value inside these composite widgets. */
const ARROW_OWNERS = [
  "[role='tab']",
  "[role='tablist']",
  "[role='radio']",
  "[role='radiogroup']",
  "[role='menuitem']",
  "[role='option']",
  "[role='tree']",
  "[role='treeitem']",
  "[role='grid']",
  "[role='gridcell']",
].join(", ");

const matches = (target: ShortcutTarget, selector: string) =>
  typeof target.closest === "function" && !!target.closest(selector);

/**
 * True when a lab shortcut for `key` may act on a keydown aimed at `target`.
 * Window, document and plain page elements qualify; fields, sliders,
 * selects, editable regions, dialogs and widgets that use the key do not.
 */
export function isLabShortcutTarget(target: unknown, key: string): boolean {
  if (!target || typeof target !== "object") return true;
  const element = target as ShortcutTarget;
  if (element.isContentEditable) return false;
  if (matches(element, EDITING) || matches(element, OVERLAY)) return false;
  if (key === " " && matches(element, SPACE_OWNERS)) return false;
  if (
    (key === "ArrowLeft" || key === "ArrowRight") &&
    matches(element, ARROW_OWNERS)
  )
    return false;
  return true;
}

/**
 * Maps a keydown to a lab action, or null when it is not ours. Ctrl, ⌘ and
 * Alt combinations always belong to the browser or the command palette.
 */
export function resolveLabShortcut(
  event: ShortcutKeyEvent,
): LabShortcut | null {
  if (event.defaultPrevented || event.isComposing) return null;
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  if (!isLabShortcutTarget(event.target, event.key)) return null;
  switch (event.key) {
    case " ":
      return event.shiftKey ? null : "toggle-play";
    case "ArrowLeft":
      return event.shiftKey ? "jump-back" : "step-back";
    case "ArrowRight":
      return event.shiftKey ? "jump-forward" : "step-forward";
    case "[":
      return "slower";
    case "]":
      return "faster";
    case "?":
      return "help";
    default:
      return null;
  }
}

/** Real time covered by one Shift+← / → press. */
export const JUMP_MS = 1000;

/**
 * Cursor after jumping about `spanMs` of real time, measured from the server
 * timestamps of the recorded events (cursor = number of events shown). Always
 * moves at least one event; unreadable timestamps degrade to a single step.
 */
export function jumpByTime(
  timestamps: readonly string[],
  cursor: number,
  direction: 1 | -1,
  spanMs = JUMP_MS,
): number {
  const total = timestamps.length;
  const current = Math.max(0, Math.min(Math.round(cursor), total));
  if (direction > 0 ? current >= total : current <= 0) return current;
  const times = timestamps.map((value) => Date.parse(value));
  // At cursor 0 nothing is shown yet; measure from the first event.
  const anchor = times[Math.max(current - 1, 0)];
  if (direction > 0) {
    let next = current + 1;
    while (next < total && times[next] - anchor <= spanMs) next++;
    return next;
  }
  let next = current - 1;
  while (next > 0 && anchor - times[next - 1] < spanMs) next--;
  return next;
}

/** Pacing presets in speed order: uniform, real-time 1×, real-time 2×. */
export const pacingCycle: readonly ReplayOptions[] = [
  { pacing: "uniform", speed: 1 },
  { pacing: "realtime", speed: 1 },
  { pacing: "realtime", speed: 2 },
];

/** `]` moves to the next preset and `[` to the previous one, wrapping around. */
export function cyclePacing(
  options: ReplayOptions,
  direction: 1 | -1,
): ReplayOptions {
  const index = options.pacing === "uniform" ? 0 : options.speed === 2 ? 2 : 1;
  const size = pacingCycle.length;
  return pacingCycle[(index + direction + size) % size];
}
