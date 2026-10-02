// Adapted from https://reactbits.dev/r/PromptBar-TS-TW.json (MIT + Commons Clause).

export const LINE = 26;

/** `/query` at the end of the draft, after the start or whitespace. */
export const parseSlash = (draft: string) => {
  const match = /(^|\s)\/(\S*)$/.exec(draft);
  return match ? match[2].toLowerCase() : null;
};
