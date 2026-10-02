import { useMemo } from "react";
import { blocksOfType, sceneBlocks } from "../../content/view";
import type { Detail } from "../../types";
import {
  annotatedLines,
  notesForFile,
  toolNames,
  type Annotation,
  type LessonCode,
  type PlacedNote,
} from "./model";

/** One entry of the notes column: an annotation or a tool's evidence button. */
export type ColumnItem =
  | { key: string; line: number; kind: "note"; note: PlacedNote }
  | { key: string; line: number; kind: "tool"; name: string };

/**
 * What sits beside the open file: its annotations (from /code, or the
 * lesson's annotated-source blocks) and an evidence button on every tool
 * function, ordered by line.
 */
export function useCodeColumn(
  detail: Detail,
  code: LessonCode | null | undefined,
  activePath: string,
) {
  const codeBlocks = sceneBlocks(detail.learning, "code");
  const annotations: Annotation[] = useMemo(
    () =>
      code?.annotations ??
      blocksOfType(codeBlocks, "annotated-source").map((block) => ({
        id: block.id,
        path: block.path,
        start: block.start ?? null,
        end: block.end ?? null,
        notes: block.notes,
        folds: block.folds,
      })),
    // codeBlocks is derived from detail.learning, which changes with the lesson.
    [code, detail.learning],
  );
  const tools = useMemo(() => toolNames(detail.tools), [detail.tools]);
  const notes = useMemo(
    () => notesForFile(annotations, activePath),
    [annotations, activePath],
  );
  const annotated = useMemo(() => annotatedLines(notes), [notes]);
  const items: ColumnItem[] = useMemo(() => {
    const file = code?.files.find((item) => item.path === activePath);
    const toolItems: ColumnItem[] = (file?.symbols ?? [])
      .filter(
        (symbol) => symbol.kind === "function" && tools.includes(symbol.name),
      )
      .map((symbol) => ({
        key: `tool:${symbol.name}:${symbol.start}`,
        line: symbol.start,
        kind: "tool",
        name: symbol.name,
      }));
    const noteItems: ColumnItem[] = notes.map((note) => ({
      key: note.key,
      line: note.line,
      kind: "note",
      note,
    }));
    return [...noteItems, ...toolItems].sort(
      (a, b) => a.line - b.line || a.key.localeCompare(b.key),
    );
  }, [code, activePath, tools, notes]);
  return {
    decisions: blocksOfType(codeBlocks, "decision"),
    annotations,
    tools,
    notes,
    annotated,
    items,
  };
}
