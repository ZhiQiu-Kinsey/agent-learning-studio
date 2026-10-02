// Adapted from https://reactbits.dev/r/JellyRadio-TS-TW.json (MIT + Commons Clause).
import { forwardRef } from "react";
import {
  motion,
  useTransform,
  type HTMLMotionProps,
  type MotionValue,
} from "motion/react";

export interface ChipValues {
  x: MotionValue<number>;
  sx: MotionValue<number>;
  sy: MotionValue<number>;
}

interface ChipProps extends HTMLMotionProps<"button"> {
  mv: ChipValues;
}

export const Chip = forwardRef<HTMLButtonElement, ChipProps>(function Chip(
  { mv, children, ...rest },
  ref,
) {
  const transform = useTransform(
    () => `translateX(${mv.x.get()}px) scale(${mv.sx.get()}, ${mv.sy.get()})`,
  );
  return (
    <motion.button ref={ref} style={{ transform }} {...rest}>
      {children}
    </motion.button>
  );
});
