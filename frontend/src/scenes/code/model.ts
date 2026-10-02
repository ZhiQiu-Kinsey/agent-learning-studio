import type { Trace } from "../../types";

/** Response of GET /api/lessons/{id}/code (see server/code_reading.py). */
export type SymbolKind = "function" | "class" | "constant";
/** context：平台代码或测试夹具里的符号，不参与“本课新增”的比较。 */
export type SymbolStatus = "added" | "changed" | "unchanged" | "context";
/** 源码在读码页里的角色：课程代码、平台代码、只服务自动化测试的夹具。 */
export type SourceRole = "lesson" | "platform" | "fixture";
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
export type SourceNote = {
  id: string;
  line: number;
  anchor?: string;
  text: string;
};
/** 展示范围内可折叠的行（通常是平台代码），界面收起为一行说明。 */
export type Fold = { id: string; start: number; end: number; label: string };
export type Annotation = {
  id: string;
  path: string;
  start: number | null;
  end: number | null;
  notes: SourceNote[];
  folds?: Fold[];
};
export type LessonCode = {
  lesson_id: string;
  files: {
    path: string;
    language: string;
    role?: SourceRole;
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

/**
 * 一个文件在读码页里怎么显示：连续可见的行，以及收起的空段。
 * - 文件里有标注块时，默认只显示各块的 start–end 范围，范围外收起为“展开其余 N 行”；
 * - 范围内的 folds（通常是平台代码）收起为一行说明；
 * - 没有标注块的文件整份显示；expanded 里的键或 showAll 会展开对应空段；
 * - 范围外少于 MIN_GAP 行或全是空行的空段直接显示，收起它们只会多一行提示。
 */
const MIN_GAP = 3;
export type CodeSegment =
  | { kind: "lines"; start: number; end: number }
  | {
      kind: "gap";
      key: string;
      start: number;
      end: number;
      reason: "outside" | "fold";
      label?: string;
    };

export function codeSegments(
  lines: readonly string[],
  annotations: readonly Annotation[],
  path: string,
  expanded: ReadonlySet<string>,
  showAll = false,
): CodeSegment[] {
  const total = lines.length;
  if (total <= 0) return [];
  const blocks = annotations.filter((block) => block.path === path);
  const hidden: (null | {
    key: string;
    reason: "outside" | "fold";
    label?: string;
  })[] = Array.from({ length: total + 1 }, () => null);
  if (blocks.length && !showAll) {
    const inside = new Array<boolean>(total + 1).fill(false);
    for (const block of blocks) {
      const start = Math.max(1, block.start ?? 1);
      const end = Math.min(total, block.end ?? total);
      for (let line = start; line <= end; line++) inside[line] = true;
    }
    for (let line = 1; line <= total; line++)
      if (!inside[line]) hidden[line] = { key: "outside", reason: "outside" };
    for (const block of blocks)
      for (const fold of block.folds ?? []) {
        const key = `fold:${block.id}:${fold.id}`;
        for (let line = fold.start; line <= Math.min(fold.end, total); line++)
          hidden[line] = { key, reason: "fold", label: fold.label };
      }
  }
  const segments: CodeSegment[] = [];
  let line = 1;
  while (line <= total) {
    const mark = hidden[line];
    let end = line;
    if (!mark) {
      while (end < total && !hidden[end + 1]) end++;
      segments.push({ kind: "lines", start: line, end });
    } else {
      while (end < total && hidden[end + 1]?.key === mark.key) end++;
      const trivial =
        mark.reason === "outside" &&
        (end - line + 1 < MIN_GAP ||
          lines.slice(line - 1, end).every((text) => !text.trim()));
      if (trivial) {
        segments.push({ kind: "lines", start: line, end });
        line = end + 1;
        continue;
      }
      const key =
        mark.reason === "outside" ? `outside:${line}-${end}` : mark.key;
      if (expanded.has(key)) segments.push({ kind: "lines", start: line, end });
      else
        segments.push({
          kind: "gap",
          key,
          start: line,
          end,
          reason: mark.reason,
          label: mark.label,
        });
    }
    line = end + 1;
  }
  // 展开的空段与相邻可见段合并成连续的一段。
  return segments.reduce<CodeSegment[]>((merged, segment) => {
    const last = merged[merged.length - 1];
    if (last?.kind === "lines" && segment.kind === "lines")
      last.end = segment.end;
    else merged.push({ ...segment });
    return merged;
  }, []);
}

/** 包含某一行的空段的键；该行可见时返回 null。 */
export function gapContaining(
  segments: readonly CodeSegment[],
  line: number,
): string | null {
  const gap = segments.find(
    (segment) =>
      segment.kind === "gap" && segment.start <= line && line <= segment.end,
  );
  return gap && gap.kind === "gap" ? gap.key : null;
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
