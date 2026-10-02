import { chapterView } from "../../content/view";
import type { Chapter } from "../../content/types.gen";
import type { BackdropName } from "../backdrops/presets";

/** A chapter with its rendered view (sections, flows, exercise, references). */
export type ChapterContent = Chapter & ReturnType<typeof chapterView>;

export const readChapter = (chapter: Chapter): ChapterContent => ({
  ...chapter,
  ...chapterView(chapter),
});

/** Self-reported checkpoints, keyed `<chapter>/<item>`; not a score. */
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
