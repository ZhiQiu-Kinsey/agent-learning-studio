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
import { animate, useMotionValue, useMotionValueEvent } from "motion/react";
import { useReducedMotion } from "../../motion";
import "./PromptBar.css";

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

const ARROW_UP = [
  12, 4.5, 18.5, 11, 14.25, 11, 14.25, 19.5, 9.75, 19.5, 9.75, 11, 5.5, 11,
];
const SQUARE = [12, 6, 18, 6, 18, 12, 18, 18, 6, 18, 6, 12, 6, 6];
const EASE_IN_OUT: [number, number, number, number] = [0.77, 0, 0.175, 1];
const LINE = 26;

const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const pathAt = (a: number[], b: number[], t: number) => {
  let d = "";
  for (let i = 0; i < a.length; i += 2)
    d += `${i ? "L" : "M"}${mix(a[i], b[i], t).toFixed(2)} ${mix(a[i + 1], b[i + 1], t).toFixed(2)}`;
  return `${d}Z`;
};

/** `/query` at the end of the draft, after the start or whitespace. */
const parseSlash = (draft: string) => {
  const match = /(^|\s)\/(\S*)$/.exec(draft);
  return match ? match[2].toLowerCase() : null;
};

function SendGlyph({ busy }: { busy: boolean }) {
  const reduce = useReducedMotion();
  const svgRef = useRef<SVGSVGElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const dir = useRef(busy ? 1 : -1);
  const t = useMotionValue(busy ? 1 : 0);
  useEffect(() => {
    const target = busy ? 1 : 0;
    dir.current = busy ? 1 : -1;
    if (t.get() === target) return undefined;
    const controls = animate(
      t,
      target,
      reduce ? { duration: 0 } : { duration: 0.24, ease: EASE_IN_OUT },
    );
    return () => controls.stop();
  }, [busy, reduce, t]);
  useMotionValueEvent(t, "change", (v) => {
    pathRef.current?.setAttribute("d", pathAt(ARROW_UP, SQUARE, v));
    const goo = reduce ? 0 : Math.sin(v * Math.PI);
    const sx = 1 - 0.12 * goo;
    if (svgRef.current)
      svgRef.current.style.transform = goo
        ? `rotate(${dir.current * 8 * goo}deg) scale(${sx}, ${1 / sx})`
        : "";
  });
  return (
    <svg
      ref={svgRef}
      className="prompt-bar__glyph"
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="currentColor"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    >
      <path ref={pathRef} d={pathAt(ARROW_UP, SQUARE, t.get())} />
    </svg>
  );
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
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
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
                <span className="prompt-bar__option-desc">
                  {row.description}
                </span>
              ) : null}
            </button>
          ))}
          {list.length === 0 ? (
            <div className="prompt-bar__empty">{labels.noMatch}</div>
          ) : null}
        </div>
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
