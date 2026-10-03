import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { stackNotes } from "./model";

export type NoteLayout = { tops: number[]; height: number };

/**
 * Aligns each notes-column item with its source line and stacks overlapping
 * ones. Re-measures when the items or the file change and on resize.
 */
export function useNoteLayout(
  items: readonly { key: string; line: number }[],
  content: string | undefined,
) {
  const frameRef = useRef<HTMLDivElement>(null);
  const notesRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef(new Map<string, HTMLElement>());
  const [layout, setLayout] = useState<NoteLayout>({ tops: [], height: 0 });

  const measure = useCallback(() => {
    const frame = frameRef.current;
    const column = notesRef.current;
    if (!frame || !column) return;
    const base = column.getBoundingClientRect().top;
    // A line folded into a collapsed gap is measured at that gap's row, so its
    // note or tool button sits next to the fold instead of piling up elsewhere.
    const rowOf = (line: number) =>
      frame.querySelector(`[data-line="${line}"]`) ??
      Array.from(
        frame.querySelectorAll<HTMLElement>("[data-start][data-end]"),
      ).find(
        (gap) =>
          Number(gap.dataset.start) <= line && line <= Number(gap.dataset.end),
      );
    const desired = items.map((item) => {
      const row = rowOf(item.line);
      return row ? row.getBoundingClientRect().top - base : 0;
    });
    const heights = items.map(
      (item) => itemRefs.current.get(item.key)?.offsetHeight ?? 0,
    );
    const tops = stackNotes(desired, heights);
    const height = tops.reduce(
      (max, top, index) => Math.max(max, top + heights[index]),
      0,
    );
    setLayout((previous) =>
      previous.height === height &&
      previous.tops.length === tops.length &&
      previous.tops.every((top, index) => Math.abs(top - tops[index]) < 0.5)
        ? previous
        : { tops, height },
    );
  }, [items]);

  useLayoutEffect(() => {
    measure();
  }, [measure, content]);

  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    if (frameRef.current) observer.observe(frameRef.current);
    if (notesRef.current) observer.observe(notesRef.current);
    return () => observer.disconnect();
  }, [measure]);

  /** Ref callback for one column item, keyed like the item. */
  const itemRef = useCallback(
    (key: string) => (element: HTMLElement | null) => {
      if (element) itemRefs.current.set(key, element);
      else itemRefs.current.delete(key);
    },
    [],
  );

  return { frameRef, notesRef, itemRef, layout };
}
