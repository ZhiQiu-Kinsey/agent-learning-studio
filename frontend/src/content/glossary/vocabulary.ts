import { createContext, useContext } from "react";
import type { GlossaryEntry } from "./match";

/**
 * What a lesson page knows about its own words: which lesson it is (so a
 * glossary term can tell "new here" from "seen before"), the bare code names
 * its source defines, and the lesson's notes for some of those names.
 */
export interface Vocabulary {
  lessonId?: string;
  /** Every source name: Chinese prose, where a bare Latin name is code. */
  names: RegExp | null;
  /** Code-shaped names only, for English prose (see `isCodeShaped`). */
  latinNames?: RegExp | null;
  notes: ReadonlyMap<string, string>;
}

export const VocabularyContext = createContext<Vocabulary>({
  names: null,
  latinNames: null,
  notes: new Map(),
});

export const useVocabulary = () => useContext(VocabularyContext);

/** new: introduced by this lesson; review: from another lesson; background: side knowledge. */
export type TermTier = "new" | "review" | "background";

export function termTier(
  entry: GlossaryEntry,
  lessonId: string | undefined,
): TermTier | undefined {
  if (entry.kind === "background") return "background";
  if (!lessonId) return undefined;
  return entry.first_lesson === lessonId ? "new" : "review";
}
