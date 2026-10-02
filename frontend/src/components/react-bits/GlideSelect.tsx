"use client";

import React, { type CSSProperties, type ReactNode } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { ArrowDown01Icon, Tick02Icon } from "@hugeicons/core-free-icons";
import { DEFAULT_OPTIONS, STYLE } from "./GlideSelect/utils";
import { useGlideSelect } from "./GlideSelect/useGlideSelect";

export interface GlideSelectOption {
  value: string;
  label: ReactNode;
  tag?: string;
}

export interface GlideSelectProps {
  options?: (string | GlideSelectOption)[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string, option: GlideSelectOption) => void;
  placeholder?: string;
  showTags?: boolean;
  accentColor?: string;
  surfaceColor?: string;
  highlightColor?: string;
  textColor?: string;
  size?: "sm" | "md" | "lg";
  radius?: number;
  menuWidth?: number;
  placement?: "top" | "bottom";
  align?: "left" | "right";
  popDuration?: number;
  glideDuration?: number;
  rememberPosition?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
  className?: string;
}

const GlideSelect: React.FC<GlideSelectProps> = ({
  options = DEFAULT_OPTIONS,
  value,
  defaultValue,
  onChange,
  placeholder = "Select…",
  showTags = true,
  accentColor = "#f5f5f5",
  surfaceColor = "#27272a",
  highlightColor = "#3f3f46",
  textColor = "#f5f5f5",
  size = "md",
  radius = 10,
  menuWidth = 176,
  placement = "bottom",
  align = "left",
  popDuration = 180,
  glideDuration = 220,
  rememberPosition = true,
  disabled = false,
  ariaLabel = "Select",
  className = "",
}) => {
  const {
    items,
    current,
    selected,
    phase,
    active,
    setActive,
    side,
    rootRef,
    triggerRef,
    menuRef,
    pillRef,
    scrub,
    id,
    S,
    popOut,
    open,
    close,
    onTriggerKey,
    onListDown,
    onListMove,
    onListUp,
    onListOver,
  } = useGlideSelect({
    options,
    value,
    defaultValue,
    onChange,
    size,
    placement,
    popDuration,
    rememberPosition,
    disabled,
  });

  const origin = `${side === "bottom" ? "top" : "bottom"} ${align}`;
  return (
    <div
      ref={rootRef}
      className={`glide-select group relative inline-block data-[disabled]:opacity-50${className ? ` ${className}` : ""}`}
      data-size={size}
      data-disabled={disabled ? "" : undefined}
      style={
        {
          "--gs-accent": accentColor,
          "--gs-surface": surfaceColor,
          "--gs-highlight": highlightColor,
          "--gs-text": textColor,
          "--gs-radius": `${radius}px`,
          "--gs-inner-radius": `${Math.max(3, radius - 4)}px`,
          "--gs-chip": `${S.chip}px`,
          "--gs-row": `${S.row}px`,
          "--gs-font": `${S.font}px`,
          "--gs-menu-w": `${menuWidth}px`,
          "--gs-pop": `${popDuration}ms`,
          "--gs-pop-out": `${popOut}ms`,
          "--gs-glide": `${glideDuration}ms`,
          "--gs-origin": origin,
        } as CSSProperties
      }
      onAnimationEnd={(e) => {
        if (e.animationName === "gs-swap" && rootRef.current)
          delete rootRef.current.dataset.swap;
      }}
    >
      <style>{STYLE}</style>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={phase === "open"}
        aria-controls={`${id}-list`}
        aria-activedescendant={active !== null ? `${id}-${active}` : undefined}
        aria-label={ariaLabel}
        disabled={disabled}
        className="glide-select__trigger group/trigger relative m-0 inline-flex cursor-pointer touch-manipulation items-center gap-1.5 border-0 pr-2 pl-2.5 leading-none font-medium outline-none select-none [-webkit-tap-highlight-color:transparent] [font-family:inherit] [height:var(--gs-chip)] [border-radius:var(--gs-inner-radius)] [background:var(--gs-surface)] [color:var(--gs-text)] [font-size:var(--gs-font)] [transition:background-color_100ms_ease,transform_160ms_cubic-bezier(0.23,1,0.32,1)] disabled:cursor-default enabled:active:scale-[0.97] motion-reduce:enabled:active:scale-100 motion-reduce:[transition:background-color_100ms_ease] aria-expanded:[background:color-mix(in_srgb,var(--gs-highlight)_60%,var(--gs-surface))] [@media(hover:hover)_and_(pointer:fine)]:enabled:hover:[background:color-mix(in_srgb,var(--gs-highlight)_60%,var(--gs-surface))]"
        onPointerDown={(e) => {
          if (e.button !== 0 || disabled) return;
          e.currentTarget.focus({ preventScroll: true });
          if (phase === "open") close("pop");
          else open(false);
        }}
        onKeyDown={onTriggerKey}
      >
        <span
          className="glide-select__label data-[empty]:opacity-60 group-data-[swap]:animate-[gs-swap_160ms_ease] motion-reduce:group-data-[swap]:animate-none"
          key={current}
          data-empty={selected < 0 ? "" : undefined}
        >
          {selected >= 0 ? items[selected].label : placeholder}
        </span>
        <span
          className="glide-select__chevron inline-flex [color:color-mix(in_srgb,var(--gs-text)_55%,transparent)] [transition:transform_200ms_cubic-bezier(0.23,1,0.32,1)] group-aria-expanded/trigger:rotate-180 motion-reduce:transition-none"
          aria-hidden="true"
        >
          <HugeiconsIcon icon={ArrowDown01Icon} size={12} strokeWidth={2.5} />
        </span>
      </button>
      {phase !== "closed" ? (
        <div
          ref={menuRef}
          className="glide-select__menu absolute z-20 min-w-full scale-95 p-1 opacity-0 [width:var(--gs-menu-w)] [border-radius:var(--gs-radius)] [background:var(--gs-surface)] [box-shadow:0_4px_16px_color-mix(in_srgb,#000_22%,transparent)] [transform-origin:var(--gs-origin)] [transition:opacity_var(--gs-pop)_cubic-bezier(0.23,1,0.32,1),transform_var(--gs-pop)_cubic-bezier(0.23,1,0.32,1)] data-[state=open]:scale-100 data-[state=open]:opacity-100 data-[state=closed]:pointer-events-none data-[state=closed]:[transition-duration:var(--gs-pop-out)] data-[side=bottom]:top-[calc(100%+6px)] data-[side=top]:bottom-[calc(100%+6px)] data-[align=left]:left-0 data-[align=right]:right-0 motion-reduce:[transform:none]! motion-reduce:[transition:opacity_var(--gs-pop)_ease] motion-reduce:data-[state=closed]:[transition-duration:var(--gs-pop-out)]"
          data-state="open"
          data-side={side}
          data-align={align}
        >
          <div
            id={`${id}-list`}
            role="listbox"
            aria-label={ariaLabel}
            className="glide-select__list group/list relative grid touch-none gap-px"
            data-live={active !== null ? "" : undefined}
            onPointerOver={onListOver}
            onPointerLeave={() => {
              if (!scrub.current && !rememberPosition) setActive(null);
            }}
            onPointerDown={onListDown}
            onPointerMove={onListMove}
            onPointerUp={onListUp}
            onPointerCancel={onListUp}
            onLostPointerCapture={onListUp}
          >
            <span
              ref={pillRef}
              className="glide-select__pill pointer-events-none absolute top-0 right-0 left-0 opacity-0 [height:var(--gs-row)] [border-radius:var(--gs-inner-radius)] [background:var(--gs-highlight)] [transition:transform_var(--gs-glide)_cubic-bezier(0.23,1,0.32,1),opacity_150ms_ease] motion-reduce:[transition:opacity_150ms_ease]"
              aria-hidden="true"
            />
            {items.map((it, i) => (
              <div
                key={it.value}
                id={`${id}-${i}`}
                role="option"
                aria-selected={i === selected}
                data-index={i}
                className="glide-select__option relative z-[1] flex cursor-pointer items-center gap-2 pr-2 pl-2.5 select-none [-webkit-tap-highlight-color:transparent] [height:var(--gs-row)] [border-radius:var(--gs-inner-radius)] [color:var(--gs-text)] [font-size:var(--gs-font)] [transition:background-color_150ms_ease] aria-selected:[background:color-mix(in_srgb,var(--gs-highlight)_60%,transparent)] group-data-[live]/list:aria-selected:bg-transparent"
              >
                <span className="glide-select__name min-w-0 flex-1 truncate font-medium">
                  {it.label}
                </span>
                {showTags && it.tag ? (
                  <span className="glide-select__tag shrink-0 [color:color-mix(in_srgb,var(--gs-text)_55%,transparent)] [font-size:calc(var(--gs-font)_-_2px)]">
                    {it.tag}
                  </span>
                ) : null}
                <span
                  className="glide-select__check inline-flex shrink-0 invisible [color:var(--gs-accent)] data-[on]:visible"
                  data-on={i === selected ? "" : undefined}
                  aria-hidden="true"
                >
                  <HugeiconsIcon
                    icon={Tick02Icon}
                    size={13}
                    strokeWidth={2.5}
                  />
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default GlideSelect;
