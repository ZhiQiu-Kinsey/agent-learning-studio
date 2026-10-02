import type { Trace } from "../../types";

/** Response of GET /api/lessons/{id}/code (see server/code_reading.py). */
export type SymbolKind = "function" | "class" | "constant";
export type SymbolStatus = "added" | "changed" | "unchanged";
export type CodeSymbol = {
  name: string;
  kind: SymbolKind;
  start: number;
  end: number;
  hash: string;
  status: SymbolStatus;
};
export type SymbolRef = {
  name: string;
  kind: SymbolKind;
  path: string;
  start: number;
  end: number;
};
export type SourceNote = { id: string; line: number; text: string };
export type Annotation = {
  id: string;
  path: string;
  start: number | null;
  end: number | null;
  notes: SourceNote[];
};
export type LessonCode = {
  lesson_id: string;
  files: {
    path: string;
    language: string;
    lines: number;
    symbols: CodeSymbol[];
  }[];
  whats_new: {
    compare_with: { id: string; number: number; title: string } | null;
    added: SymbolRef[];
    changed: SymbolRef[];
    unchanged: SymbolRef[];
  };
  annotations: Annotation[];
};

/** Same line rules as the backend: only \r\n, \r and \n break lines; a final newline adds no line. */
export function splitLines(text: string): string[] {
  const lines = text.split(/\r\n|\r|\n/);
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  return lines;
}

/** Minimal shape of a Prism token stream, so the splitter is testable without Prism. */
export type TokenLike =
  | string
  | {
      type: string;
      alias?: string | string[];
      content: TokenLike | TokenLike[];
    };
export type Segment = { text: string; types: string[] };

/**
 * Break a highlighted token stream into per-line segments. Multi-line tokens
 * (docstrings, triple-quoted strings) keep their classes on every line they span.
 */
export function tokenLines(stream: TokenLike | TokenLike[]): Segment[][] {
  const lines: Segment[][] = [[]];
  const walk = (token: TokenLike, types: string[]) => {
    if (typeof token === "string") {
      token.split(/\r\n|\r|\n/).forEach((part, index) => {
        if (index > 0) lines.push([]);
        if (part) lines[lines.length - 1].push({ text: part, types });
      });
      return;
    }
    const aliases =
      token.alias === undefined
        ? []
        : Array.isArray(token.alias)
          ? token.alias
          : [token.alias];
    const next = [...types, token.type, ...aliases];
    const content = Array.isArray(token.content)
      ? token.content
      : [token.content];
    content.forEach((child) => walk(child, next));
  };
  (Array.isArray(stream) ? stream : [stream]).forEach((token) =>
    walk(token, []),
  );
  if (lines.length > 1 && lines[lines.length - 1].length === 0) lines.pop();
  return lines;
}

/** One note placed on a file, remembering which annotated-source block it came from. */
export type PlacedNote = SourceNote & { block: string; key: string };

export function notesForFile(
  annotations: readonly Annotation[],
  path: string,
): PlacedNote[] {
  return annotations
    .filter((block) => block.path === path)
    .flatMap((block) =>
      block.notes.map((note) => ({
        ...note,
        block: block.id,
        key: `${block.id}:${note.id}`,
      })),
    )
    .sort((a, b) => a.line - b.line || a.key.localeCompare(b.key));
}

/** Lines that carry a note, highlighted in the code column. */
export function annotatedLines(notes: readonly PlacedNote[]): Set<number> {
  return new Set(notes.map((note) => note.line));
}

/**
 * Align note cards with their lines. Each card wants to start at its line's
 * top; when an earlier card is taller than the gap between lines, later cards
 * are pushed down instead of overlapping. Inputs are in display order.
 */
export function stackNotes(
  desired: readonly number[],
  heights: readonly number[],
  gap = 8,
): number[] {
  const tops: number[] = [];
  let floor = -Infinity;
  desired.forEach((want, index) => {
    const top = Math.max(want, floor);
    tops.push(top);
    floor = top + (heights[index] ?? 0) + gap;
  });
  return tops;
}

/** Function names declared in a lesson's TOOLS list (OpenAI-style tool schema). */
export function toolNames(tools: unknown): string[] {
  if (!Array.isArray(tools)) return [];
  return tools.flatMap((tool) => {
    const name = (tool as { function?: { name?: unknown } } | null)?.function
      ?.name;
    return typeof name === "string" && name ? [name] : [];
  });
}

/** Index of the latest real tool_result for this tool, or -1 when the run has none. */
export function latestToolResult(
  events: readonly Trace[],
  name: string,
): number {
  for (let index = events.length - 1; index >= 0; index--) {
    const event = events[index];
    if (event.type === "tool_result" && event.data.name === name) return index;
  }
  return -1;
}

/** Added and changed symbols, in source order, for the “本课新增” card. */
export function whatsNewItems(code: LessonCode) {
  const order = new Map(code.files.map((file, index) => [file.path, index]));
  return [
    ...code.whats_new.added.map((item) => ({
      ...item,
      status: "added" as const,
    })),
    ...code.whats_new.changed.map((item) => ({
      ...item,
      status: "changed" as const,
    })),
  ].sort(
    (a, b) =>
      (order.get(a.path) ?? 0) - (order.get(b.path) ?? 0) || a.start - b.start,
  );
}
