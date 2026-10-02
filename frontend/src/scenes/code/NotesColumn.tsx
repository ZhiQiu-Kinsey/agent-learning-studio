import type { CSSProperties, Ref } from "react";
import { useTranslation } from "react-i18next";
import { EvidenceButton } from "./EvidenceButton";
import type { ColumnItem } from "./useCodeColumn";
import type { Evidence } from "./useEvidence";
import type { NoteLayout } from "./useNoteLayout";

/** Annotations and tool evidence beside the source, each aligned to its line. */
export function NotesColumn({
  items,
  layout,
  columnRef,
  itemRef,
  activeNote,
  onNote,
  evidence,
  onOpenEvidence,
}: {
  items: ColumnItem[];
  layout: NoteLayout;
  columnRef: Ref<HTMLDivElement>;
  itemRef: (key: string) => (element: HTMLElement | null) => void;
  activeNote: string | null;
  onNote: (key: string, line: number) => void;
  evidence: Evidence | null;
  onOpenEvidence: (name: string, at: string) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  return (
    <aside
      className="code-notes"
      data-testid="code-notes"
      aria-label={t("notes")}
      ref={columnRef}
      style={{ "--notes-height": `${layout.height}px` } as CSSProperties}
    >
      {items.length === 0 && (
        <p className="code-notes-empty">{t("notesEmpty")}</p>
      )}
      {items.map((item, index) => (
        <div
          key={item.key}
          className="code-note-slot"
          data-kind={item.kind}
          ref={itemRef(item.key)}
          style={
            {
              "--note-top": `${layout.tops[index] ?? 0}px`,
              "--i": index,
            } as CSSProperties
          }
        >
          {item.kind === "note" ? (
            <button
              type="button"
              className="code-note"
              data-testid="code-note"
              data-line={item.line}
              aria-pressed={activeNote === item.key}
              aria-label={t("jumpToLine", { line: item.line })}
              onClick={() => onNote(item.key, item.line)}
            >
              <span className="code-note-line">
                {t("noteLine", { line: item.line })}
              </span>
              <span className="code-note-text">{item.note.text}</span>
            </button>
          ) : (
            <EvidenceButton
              name={item.name}
              at={item.key}
              evidence={evidence}
              onOpen={onOpenEvidence}
            />
          )}
        </div>
      ))}
    </aside>
  );
}
