import type { Block } from "../view";

/**
 * Glossary-eligible texts of a block in reading order. Must list the exact
 * strings the renderers pass to <GlossaryText> / <GlossaryMarkdown>.
 */
export function blockTexts(block: Block): string[] {
  switch (block.type) {
    case "concepts":
      return block.items.map((item) => item.description);
    case "prose":
      return block.paragraphs;
    case "walkthrough":
      return block.steps.map((step) => step.body);
    case "steps":
      return [...block.paragraphs, ...block.items.map((item) => item.text)];
    case "compare":
      return [...block.paragraphs, ...block.rows.flat()];
    case "callout":
      return block.paragraphs;
    case "misconception":
      return [block.claim, block.correction];
    case "deep-dive":
      return [...(block.summary ? [block.summary] : []), ...block.paragraphs];
    default:
      return [];
  }
}

/**
 * Glossary-eligible texts of a list of blocks in claiming order: every
 * non-deep-dive block first, then all deep-dives. A deep-dive is folded by
 * default, so a term that also appears in the main text is marked there; a
 * term only a deep-dive uses is still claimed by it. Keep in step with
 * `marked_texts` in server/vocabulary.py.
 */
export function readingTexts(blocks: readonly Block[]): string[] {
  const isDive = (block: Block) => block.type === "deep-dive";
  return [
    ...blocks.filter((block) => !isDive(block)).flatMap(blockTexts),
    ...blocks.filter(isDive).flatMap(blockTexts),
  ];
}
