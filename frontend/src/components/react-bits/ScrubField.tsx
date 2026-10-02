// Adapted from https://reactbits.dev/r/ScrubField-TS-TW.json (MIT + Commons Clause, see LICENSE.md).
// Change: reduced motion follows the app-wide motion level instead of the OS query alone.
"use client";

import React from "react";
import { motion, type MotionStyle } from "motion/react";
import { onColor } from "./ScrubField/utils";
import { useScrubField } from "./ScrubField/useScrubField";

export type ScrubFieldSize = "sm" | "md" | "lg";

export interface ScrubFieldProps {
  label?: string;
  suffix?: string;
  value?: number;
  defaultValue?: number;
  min?: number;
  max?: number;
  step?: number;
  size?: ScrubFieldSize;
  sensitivity?: number;
  rubberReach?: number;
  returnDuration?: number;
  coarseMultiplier?: number;
  fineMultiplier?: number;
  showDelta?: boolean;
  showDirty?: boolean;
  showFill?: boolean;
  accent?: string;
  chipColor?: string;
  disabled?: boolean;
  onChange?: (value: number) => void;
  onCommit?: (value: number) => void;
  className?: string;
}

const ScrubField: React.FC<ScrubFieldProps> = ({
  label = "Radius",
  suffix = "px",
  value: valueProp,
  defaultValue = 24,
  min = 0,
  max = 100,
  step = 1,
  size = "md",
  sensitivity = 2,
  rubberReach = 8,
  returnDuration = 300,
  coarseMultiplier = 10,
  fineMultiplier = 0.1,
  showDelta = true,
  showDirty = false,
  showFill = true,
  accent = "#f5f5f5",
  chipColor = "#27272a",
  disabled = false,
  onChange,
  onCommit,
  className = "",
}) => {
  const {
    id,
    value,
    dragging,
    draft,
    setDraft,
    chipRef,
    inputRef,
    ghostRef,
    movedRef,
    preset,
    fmt,
    chipTransform,
    fillTransform,
    handlePointerDown,
    handlePointerMove,
    end,
    handleKeyDown,
    handleFocus,
    handleBlur,
    dirty,
  } = useScrubField({
    valueProp,
    defaultValue,
    min,
    max,
    step,
    size,
    sensitivity,
    rubberReach,
    returnDuration,
    coarseMultiplier,
    fineMultiplier,
    showDirty,
    disabled,
    onChange,
    onCommit,
  });

  return (
    <motion.div
      ref={chipRef}
      className={`group relative inline-flex h-[var(--sf-h)] w-[var(--sf-w)] items-center gap-1 rounded-[var(--sf-r)] pl-1 pr-2 leading-none select-none isolate [font-family:inherit] [font-size:var(--sf-fs)] [background:var(--sf-chip)] [box-shadow:0_0_0_1px_transparent] cursor-ew-resize touch-pan-y data-[typing=true]:cursor-text data-[disabled=true]:cursor-default [-webkit-tap-highlight-color:transparent] [-webkit-touch-callout:none] [transition:background-color_200ms_ease,box-shadow_200ms_ease] data-[dirty=true]:[box-shadow:0_0_0_1px_color-mix(in_srgb,var(--sf-accent)_55%,transparent)] data-[dirty=true]:[transition-duration:0ms] data-[typing=true]:[background:color-mix(in_srgb,currentColor_7%,var(--sf-chip))] data-[disabled=true]:opacity-50${className ? ` ${className}` : ""}`}
      data-dirty={dirty ? "true" : "false"}
      data-dragging={dragging ? "true" : "false"}
      data-typing={draft !== null ? "true" : "false"}
      data-disabled={disabled ? "true" : "false"}
      aria-disabled={disabled || undefined}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={() => end()}
      onPointerCancel={() => end(true)}
      onLostPointerCapture={() => end()}
      style={
        {
          "--sf-accent": accent,
          "--sf-chip": chipColor,
          "--sf-ghost-ink": onColor(accent),
          "--sf-h": `${preset.height}px`,
          "--sf-fs": `${preset.font}px`,
          "--sf-r": `${preset.radius}px`,
          "--sf-w": `${preset.width}px`,
          "--sf-ease-out": "cubic-bezier(0.23, 1, 0.32, 1)",
          transform: chipTransform,
        } as MotionStyle
      }
    >
      {showFill ? (
        <span
          className="pointer-events-none absolute inset-0 -z-10 overflow-hidden rounded-[inherit]"
          aria-hidden="true"
        >
          <motion.span
            className="absolute inset-0 origin-left [background:color-mix(in_srgb,var(--sf-accent)_16%,transparent)]"
            style={{ transform: fillTransform }}
          />
        </span>
      ) : null}
      <label
        htmlFor={id}
        className="inline-flex h-full cursor-[inherit] items-center whitespace-nowrap rounded-[calc(var(--sf-r)-2px)] px-1.5 font-medium [color:color-mix(in_srgb,currentColor_55%,transparent)] [transition:color_120ms_ease,transform_160ms_var(--sf-ease-out)] [@media(hover:hover)_and_(pointer:fine)]:group-data-[disabled=false]:group-hover:[color:color-mix(in_srgb,currentColor_85%,transparent)] group-data-[disabled=false]:group-data-[typing=false]:group-active:[transform:scale(0.96)] group-data-[disabled=false]:group-data-[typing=false]:group-active:[color:currentColor] group-data-[dragging=true]:[transform:scale(0.96)] group-data-[dragging=true]:[color:currentColor] motion-reduce:[transition:color_120ms_ease] motion-reduce:group-data-[dragging=true]:[transform:none] motion-reduce:group-data-[disabled=false]:group-data-[typing=false]:group-active:[transform:none]"
        onClick={(e) => {
          if (movedRef.current) e.preventDefault();
        }}
      >
        {label}
      </label>
      <input
        ref={inputRef}
        id={id}
        className="m-0 w-full min-w-0 flex-1 cursor-[inherit] border-0 bg-transparent p-0 text-right font-medium tabular-nums outline-0 [color:inherit] [font-family:inherit] [font-size:inherit] [transition:color_120ms_ease] group-data-[typing=true]:cursor-text group-data-[over=true]:[color:color-mix(in_srgb,currentColor_55%,transparent)]"
        type="text"
        inputMode="decimal"
        role="spinbutton"
        aria-valuenow={value}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuetext={`${fmt(value)}${suffix ? ` ${suffix}` : ""}`}
        defaultValue={fmt(value)}
        disabled={disabled}
        onFocus={handleFocus}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
      />
      {suffix ? (
        <span
          className="font-medium [color:color-mix(in_srgb,currentColor_45%,transparent)]"
          aria-hidden="true"
        >
          {suffix}
        </span>
      ) : null}
      {showDelta ? (
        <span
          ref={ghostRef}
          className="pointer-events-none absolute -top-1.5 left-0 origin-bottom whitespace-nowrap rounded-full px-1.5 py-0.5 text-[11px] leading-[1.4] font-semibold tabular-nums opacity-0 [color:var(--sf-ghost-ink)] [translate:0_-100%] [scale:0.95] [background:var(--sf-accent)] [transition:opacity_125ms_var(--sf-ease-out),scale_125ms_var(--sf-ease-out)] group-data-[dragging=true]:opacity-100 group-data-[dragging=true]:[scale:1] motion-reduce:[scale:1] motion-reduce:[transition:opacity_200ms_ease]"
          aria-hidden="true"
        />
      ) : null}
    </motion.div>
  );
};

export default ScrubField;
