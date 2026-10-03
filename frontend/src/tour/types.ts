import type { ReactNode } from "react";

/**
 * Where a tour step points. `element` steps frame what `find` returns
 * (`frame` may return a smaller or larger box to frame instead, e.g. the
 * visible part of a scroll container); `center` steps dim the whole page and
 * show the card in the middle.
 */
export type TourTarget =
  | {
      kind: "element";
      find: () => HTMLElement | null;
      frame?: () => HTMLElement | null;
    }
  | { kind: "center" };

/** One step of a masked tour: what to frame, how to get there, what to say. */
export type TourStep = {
  id: string;
  target: TourTarget;
  /** Runs before the step shows: switch views, select data, wait for render. */
  prepare?: () => Promise<void>;
  /** Short label above the text, e.g. who the step is about. */
  badge?: ReactNode;
  body: ReactNode;
};
