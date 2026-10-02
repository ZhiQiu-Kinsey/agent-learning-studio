// Adapted from https://reactbits.dev/r/GlideSelect-TS-TW.json (MIT + Commons Clause).
import type { GlideSelectOption } from "../GlideSelect";

export type Phase = "closed" | "open" | "closing";

export const SIZES: Record<
  string,
  { chip: number; row: number; font: number }
> = {
  sm: { chip: 28, row: 26, font: 12 },
  md: { chip: 32, row: 30, font: 13 },
  lg: { chip: 44, row: 40, font: 14 },
};
export const PAD = 4;
export const GAP = 1;
export const MENU_GAP = 6;
export const DEFAULT_OPTIONS: (string | GlideSelectOption)[] = [
  "One",
  "Two",
  "Three",
];
export const STYLE = "@keyframes gs-swap{from{opacity:.6;filter:blur(2px)}}";

export const norm = (o: string | GlideSelectOption): GlideSelectOption =>
  typeof o === "string" ? { value: o, label: o } : o;
const textOf = (it: GlideSelectOption) =>
  typeof it.label === "string" ? it.label : it.value;
export const typeaheadIndex = (
  items: GlideSelectOption[],
  from: number,
  ch: string,
) => {
  const c = ch.toLowerCase();
  const n = items.length;
  for (let k = 1; k <= n; k++) {
    const i = (from + k) % n;
    if (textOf(items[i]).toLowerCase().startsWith(c)) return i;
  }
  return from;
};
