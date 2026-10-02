// Adapted from https://reactbits.dev/r/ThoughtLine-TS-TW.json (MIT + Commons Clause).
import { HugeiconsIcon } from "@hugeicons/react";
import { Tick02Icon } from "@hugeicons/core-free-icons";

interface TraceStepsProps {
  steps: string[];
  isWorking: boolean;
  open: boolean;
}

/** The foldable list of reasoning steps under the head line; the last step pulses while working. */
export function TraceSteps({ steps, isWorking, open }: TraceStepsProps) {
  return (
    <div
      className="thought-line__trace grid w-0 min-w-full [grid-template-rows:0fr] [transition:grid-template-rows_var(--tl-settle)_cubic-bezier(0.23,1,0.32,1)] data-[open]:[grid-template-rows:1fr]"
      data-open={open ? "" : undefined}
      aria-hidden={!open}
    >
      <div className="thought-line__fold min-h-0 overflow-x-visible overflow-y-clip">
        <div className="thought-line__steps flex w-max flex-col gap-[0.45em] pt-[0.6em] pb-[0.2em] pl-[1.6em] text-[0.875em] font-normal whitespace-nowrap">
          {steps.map((text, i) => {
            const done = !isWorking || i < steps.length - 1;
            return (
              <div
                key={`${i}-${text}`}
                className="thought-line__step group/step flex translate-y-0 items-center gap-[0.5em] opacity-100 [transition:opacity_200ms_cubic-bezier(0.23,1,0.32,1),transform_200ms_cubic-bezier(0.23,1,0.32,1)] starting:-translate-y-1 starting:opacity-0 motion-reduce:[transform:none]! motion-reduce:[transition:opacity_200ms_ease]"
                data-done={done ? "" : undefined}
              >
                <span
                  className="thought-line__mark inline-grid h-[1em] w-[1em] flex-none place-items-center opacity-55"
                  aria-hidden="true"
                >
                  {done ? (
                    <HugeiconsIcon
                      icon={Tick02Icon}
                      size="1em"
                      strokeWidth={2.5}
                    />
                  ) : (
                    <i className="thought-line__pulse block h-[0.4em] w-[0.4em] rounded-full bg-current [animation:thought-line-pulse_1.6s_cubic-bezier(0.77,0,0.175,1)_infinite] motion-reduce:[animation-duration:2.4s]" />
                  )}
                </span>
                <span className="thought-line__step-text [transition:opacity_var(--tl-settle)_ease] group-data-[done]/step:opacity-55">
                  {text}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
