import { chapterView } from "../../content/view";
import type { Chapter } from "../../content/types.gen";
import { blockTexts } from "../../content/glossary/texts";
import type { BackdropName } from "../backdrops/presets";

/** A chapter with its rendered view (sections, attachments, exercise, references). */
export type ChapterContent = Chapter & ReturnType<typeof chapterView>;

export const readChapter = (chapter: Chapter): ChapterContent => ({
  ...chapter,
  ...chapterView(chapter),
});

/**
 * Glossary-eligible texts in reading order: opening attachments, then each
 * section followed by the attachments authored after it. Mirrors the render
 * order so the first occurrence of a term is the one the learner meets first.
 */
export function chapterGlossaryTexts(chapter: ChapterContent): string[] {
  const after = (id: string | null) =>
    chapter.attachments
      .filter((attachment) => attachment.after === id)
      .flatMap(({ block }) => blockTexts(block));
  return [
    ...after(null),
    ...chapter.sections.flatMap((section) => [
      ...section.paragraphs,
      ...(section.bullets ?? []),
      ...(section.table?.rows.flat() ?? []),
      ...after(section.id),
    ]),
  ];
}

/** Self-reported checkpoints,keyed `<chapter>/<item>`; not a score. */
export type CheckedPoints = Record<string, string>;

export function chapterChecks(chapter: Chapter, checked: CheckedPoints) {
  const points = chapterView(chapter).exercise.checkpoints;
  return {
    total: points.length,
    done: points.filter((point) => checked[`${chapter.id}/${point.id}`]).length,
  };
}

/** Every chapter has its own sky (distinct hues, so the tabs differ); unknown chapters cycle. */
const chapterSkies: Record<string, BackdropName> = {
  intro: "galaxy",
  "what-is-agent": "web",
  "learning-path": "rays",
  "lab-evidence": "radar",
};
const skyCycle: BackdropName[] = ["aurora", "web", "rays", "radar", "veil"];
export const skyFor = (id: string, index: number): BackdropName =>
  chapterSkies[id] ?? skyCycle[index % skyCycle.length];

/** "01", "02", … for chapter and section numerals. */
export const numeral = (index: number) => String(index + 1).padStart(2, "0");
