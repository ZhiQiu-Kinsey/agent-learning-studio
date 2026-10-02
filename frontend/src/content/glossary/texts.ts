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
    default:
      return [];
  }
}
