// Adapted from https://reactbits.dev/r/PromptBar-TS-TW.json (MIT + Commons Clause).
// Changes: trimmed to what the lab really does — a controlled text field, a `/`
// command menu supplied by the caller, and one send button that morphs into a
// stop button while busy. The upstream model picker, effort slider, dictation,
// attachments and @ sources are removed (they would be non-functional here).
// All copy comes from the caller; motion follows the app motion level.
import React, {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import "./PromptBar.css";
import { SendGlyph } from "./PromptBar/SendGlyph";
import { LINE, parseSlash } from "./PromptBar/utils";
import { CommandMenu } from "./PromptBar/CommandMenu";

export interface PromptBarCommand {
  key: string;
  name: string;
  description?: string;
  active?: boolean;
}

export interface PromptBarProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  /** True while a run is in progress: the button becomes "stop". */
  busy?: boolean;
  /** Whether sending is currently allowed (validation lives with the caller). */
  canSend?: boolean;
  /** Disables the text field (the button still stops a busy run). */
  disabled?: boolean;
  commands?: PromptBarCommand[];
  onCommand?: (key: string) => void;
  placeholder?: string;
  labels: {
    send: string;
    sendText?: string;
    stop: string;
    stopText?: string;
    commands: string;
    openCommands: string;
    noMatch: string;
  };
  hint?: ReactNode;
  minRows?: number;
  maxRows?: number;
  textareaProps?: TextareaHTMLAttributes<HTMLTextAreaElement> & {
    "data-testid"?: string;
  };
  sendTestId?: string;
  stopTestId?: string;
  className?: string;
}

const PromptBar: React.FC<PromptBarProps> = ({
  value,
  onChange,
  onSend,
  onStop,
  busy = false,
  canSend = true,
  disabled = false,
  commands = [],
  onCommand,
  placeholder,
  labels,
  hint,
  minRows = 4,
  maxRows = 10,
  textareaProps,
  sendTestId,
  stopTestId,
  className = "",
}) => {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const glowRef = useRef<HTMLSpanElement>(null);
  const rowRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [dismissed, setDismissed] = useState(false);
  const [manual, setManual] = useState(false);
  const [active, setActive] = useState(0);
  const [pressed, setPressed] = useState(false);

  const slash = dismissed || disabled ? null : parseSlash(value);
  const open = !disabled && commands.length > 0 && (manual || slash !== null);
  const query = manual ? "" : (slash ?? "");
  const list = useMemo(
    () =>
      open
        ? commands.filter(
            (item) =>
              !query ||
              item.name.toLowerCase().includes(query) ||
              item.key.toLowerCase().startsWith(query),
          )
        : [],
    [open, query, commands],
  );
  const cursor = Math.min(active, Math.max(0, list.length - 1));
  const armed = busy || canSend;

  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    const min = LINE * minRows;
    const max = LINE * maxRows;
    el.style.height = `${Math.max(min, Math.min(el.scrollHeight, max))}px`;
    el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
  }, [value, minRows, maxRows]);

  useLayoutEffect(() => {
    const glow = glowRef.current;
    if (!glow || !open) return;
    const row = rowRefs.current[cursor];
    if (!row) {
      glow.style.opacity = "0";
      return;
    }
    glow.style.top = `${row.offsetTop}px`;
    glow.style.height = `${row.offsetHeight}px`;
    glow.style.opacity = "1";
  }, [open, cursor, list]);

  useEffect(() => {
    if (!manual) return undefined;
    const onDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setManual(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [manual]);

  const focusInput = () => inputRef.current?.focus({ preventScroll: true });
  const close = () => {
    setManual(false);
    setDismissed(true);
  };
  const pick = (key: string) => {
    // Drop the typed `/query`; the caller decides what the command does.
    if (slash !== null) onChange(value.replace(/(^|\s)\/\S*$/, "$1").trimEnd());
    setManual(false);
    setDismissed(false);
    onCommand?.(key);
    focusInput();
  };
  const submit = () => {
    if (busy) onStop?.();
    else if (canSend) {
      close();
      onSend();
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    textareaProps?.onKeyDown?.(event);
    if (event.defaultPrevented) return;
    if (open && list.length) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        setActive(
          (cursor + (event.key === "ArrowDown" ? 1 : list.length - 1)) %
            list.length,
        );
        return;
      }
      if ((event.key === "Enter" && !event.shiftKey) || event.key === "Tab") {
        event.preventDefault();
        pick(list[cursor].key);
        return;
      }
    }
    if (event.key === "Escape" && open) {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    // Ctrl/⌘+Enter runs: a real model run costs money, so a plain Enter
    // only inserts a newline and never submits by accident.
    if (
      event.key === "Enter" &&
      (event.ctrlKey || event.metaKey) &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      if (!busy) submit();
    }
  };

  return (
    <div
      ref={rootRef}
      className={`prompt-bar${className ? ` ${className}` : ""}`}
      data-busy={busy ? "" : undefined}
      data-disabled={disabled ? "" : undefined}
    >
      {open ? (
        <CommandMenu
          listId={listId}
          labels={labels}
          glowRef={glowRef}
          list={list}
          rowRefs={rowRefs}
          cursor={cursor}
          setActive={setActive}
          pick={pick}
        />
      ) : null}
      <div
        className="prompt-bar__box"
        role="presentation"
        onClick={(event) => {
          if (event.target === event.currentTarget) focusInput();
        }}
      >
        <textarea
          {...textareaProps}
          ref={inputRef}
          className="prompt-bar__input"
          rows={minRows}
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={
            open && list.length ? `${listId}-${cursor}` : undefined
          }
          onChange={(event) => {
            onChange(event.target.value);
            setDismissed(false);
            setManual(false);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
        />
        <div className="prompt-bar__toolbar">
          {commands.length > 0 ? (
            <button
              type="button"
              className="prompt-bar__tool"
              aria-label={labels.openCommands}
              aria-expanded={open}
              aria-controls={open ? listId : undefined}
              disabled={disabled}
              data-on={open ? "" : undefined}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                setActive(
                  Math.max(
                    0,
                    commands.findIndex((item) => item.active),
                  ),
                );
                setDismissed(false);
                setManual((v) => !v);
                focusInput();
              }}
            >
              <span aria-hidden="true">/</span>
            </button>
          ) : null}
          {hint ? <span className="prompt-bar__hint">{hint}</span> : null}
          <span className="prompt-bar__spacer" />
          <button
            type="button"
            className="prompt-bar__send"
            disabled={!armed}
            aria-label={busy ? labels.stop : labels.send}
            data-testid={busy ? stopTestId : sendTestId}
            data-armed={armed ? "" : undefined}
            data-pressed={pressed ? "" : undefined}
            onPointerDown={(event) => {
              if (event.button === 0 && armed) setPressed(true);
            }}
            onPointerUp={() => setPressed(false)}
            onPointerCancel={() => setPressed(false)}
            onPointerLeave={() => setPressed(false)}
            onClick={submit}
          >
            <SendGlyph busy={busy} />
            {(busy ? labels.stopText : labels.sendText) ? (
              <span aria-hidden="true">
                {busy ? labels.stopText : labels.sendText}
              </span>
            ) : null}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PromptBar;
