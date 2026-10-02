// Adapted from https://reactbits.dev/r/PromptBar-TS-TW.json (MIT + Commons Clause).
import type { RefObject } from "react";
import type { PromptBarCommand, PromptBarProps } from "../PromptBar";

interface CommandMenuProps {
  listId: string;
  labels: PromptBarProps["labels"];
  glowRef: RefObject<HTMLSpanElement | null>;
  list: PromptBarCommand[];
  rowRefs: RefObject<(HTMLButtonElement | null)[]>;
  cursor: number;
  setActive: (index: number) => void;
  pick: (key: string) => void;
}

/** The `/` command list with its gliding highlight; rows never take focus from the text field. */
export function CommandMenu({
  listId,
  labels,
  glowRef,
  list,
  rowRefs,
  cursor,
  setActive,
  pick,
}: CommandMenuProps) {
  return (
    <div
      className="prompt-bar__menu"
      role="listbox"
      id={listId}
      aria-label={labels.commands}
    >
      <span ref={glowRef} className="prompt-bar__glow" aria-hidden="true" />
      {list.map((row, index) => (
        <button
          key={row.key}
          id={`${listId}-${index}`}
          ref={(el) => {
            rowRefs.current[index] = el;
          }}
          type="button"
          role="option"
          tabIndex={-1}
          aria-selected={index === cursor}
          data-current={row.active ? "" : undefined}
          className="prompt-bar__option"
          onMouseDown={(event) => event.preventDefault()}
          onPointerEnter={() => setActive(index)}
          onClick={() => pick(row.key)}
        >
          <span className="prompt-bar__slash" aria-hidden="true">
            /
          </span>
          <span className="prompt-bar__option-name">{row.name}</span>
          {row.description ? (
            <span className="prompt-bar__option-desc">{row.description}</span>
          ) : null}
        </button>
      ))}
      {list.length === 0 ? (
        <div className="prompt-bar__empty">{labels.noMatch}</div>
      ) : null}
    </div>
  );
}
