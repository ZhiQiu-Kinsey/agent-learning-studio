/**
 * Text layout for the canvas-drawn badge face. Canvas has no line breaking of
 * its own, so these helpers wrap and shrink text by measured width. They take
 * a `measure` callback instead of a canvas context so they stay pure.
 */

/** Width of `text` at a given font size, in the same units as `maxWidth`. */
export type Measure = (text: string, size: number) => number;

// CJK ideographs, kana, Hangul and full-width forms: a line may break between
// any two of these characters.
const CJK =
  "\\u2E80-\\u2FFF\\u3040-\\u30FF\\u3100-\\u31FF\\u3400-\\u4DBF\\u4E00-\\u9FFF\\uAC00-\\uD7AF\\uF900-\\uFAFF";
// Punctuation that must not start a line; it sticks to the token before it.
const NO_LINE_START = "\\u3001\\u3002\\uFF0C\\uFF0E\\uFF1A\\uFF1B\\uFF01\\uFF1F\\uFF09\\u300B\\u300D\\u300F\\u3011\\u201D\\u2019";
const TOKEN = new RegExp(
  `\\s+|[${CJK}\\u3000-\\u303F\\uFF00-\\uFFEF][${NO_LINE_START}]*|[^\\s${CJK}\\u3000-\\u303F\\uFF00-\\uFFEF]+[${NO_LINE_START}]*`,
  "gu",
);

/**
 * Split text into break units: runs of whitespace, single CJK characters
 * (with any trailing closing punctuation) and whole Latin words.
 */
export function tokenize(text: string): string[] {
  return text.match(TOKEN) ?? [];
}

/**
 * Wrap text into lines no wider than `maxWidth`. Latin text breaks between
 * words, CJK text between characters; a single word wider than the line is
 * the only thing broken mid-word. Spaces inside a line are kept as written
 * (the brand line is letter-spaced with them); line ends are trimmed.
 */
export function wrapText(
  text: string,
  maxWidth: number,
  measure: (text: string) => number,
): string[] {
  const lines: string[] = [];
  let line = "";
  const push = () => {
    const trimmed = line.trimEnd();
    if (trimmed) lines.push(trimmed);
    line = "";
  };
  for (const token of tokenize(text.trim())) {
    if (/^\s+$/u.test(token)) {
      if (line) line += token;
      continue;
    }
    if (measure(line + token) <= maxWidth) {
      line += token;
      continue;
    }
    if (line.trim()) push();
    if (measure(token) <= maxWidth) {
      line = token;
      continue;
    }
    // A word too long for any line: break it by character.
    for (const char of Array.from(token)) {
      if (line && measure(line + char) > maxWidth) push();
      line += char;
    }
  }
  push();
  return lines;
}

/**
 * Keep at most `maxLines`; when text is cut, the last kept line ends in an
 * ellipsis that still fits `maxWidth`.
 */
export function clampLines(
  lines: string[],
  maxLines: number,
  maxWidth: number,
  measure: (text: string) => number,
): string[] {
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  let last = Array.from(kept[maxLines - 1]);
  while (last.length && measure(`${last.join("").trimEnd()}…`) > maxWidth)
    last = last.slice(0, -1);
  kept[maxLines - 1] = `${last.join("").trimEnd()}…`;
  return kept;
}

export interface FitStep {
  size: number;
  maxLines: number;
}

/**
 * Try each (size, maxLines) step in order and use the first where the wrapped
 * text fits without cutting; if none fits, the last step is used and clamped
 * with an ellipsis. Every returned line fits `maxWidth` at the returned size.
 */
export function fitText(
  text: string,
  maxWidth: number,
  steps: FitStep[],
  measure: Measure,
): { size: number; lines: string[] } {
  for (const [index, step] of steps.entries()) {
    const at = (value: string) => measure(value, step.size);
    const lines = wrapText(text, maxWidth, at);
    if (lines.length <= step.maxLines || index === steps.length - 1)
      return {
        size: step.size,
        lines: clampLines(lines, step.maxLines, maxWidth, at),
      };
  }
  return { size: 0, lines: [] };
}
