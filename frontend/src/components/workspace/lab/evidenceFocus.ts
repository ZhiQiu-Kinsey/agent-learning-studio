import { createContext, useContext } from "react";

/**
 * The evidence the lab is pointing at: one event of the learner's own run and,
 * optionally, a field inside it (a selector path relative to the event, e.g.
 * `data.body.messages`). Set by the guided replay and by an observe point's
 * "locate"; the bench switches to the execution record and the inspector frames
 * that field.
 */
export type EvidenceFocus = {
  index: number;
  path: string | null;
  /** Scroll the framed field into view. The guided replay scrolls by itself. */
  reveal: boolean;
};

export const EvidenceFocusContext = createContext<EvidenceFocus | null>(null);

export const useEvidenceFocus = () => useContext(EvidenceFocusContext);
