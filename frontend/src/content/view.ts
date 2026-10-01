import type {
  Chapter,
  BlockScene,
  LessonContent,
  ObservePoint,
  QuizQuestion,
} from "./types.gen";

export type Block = BlockScene["blocks"][number];
export type BlockOf<T extends Block["type"]> = Extract<Block, { type: T }>;
export type Scene = "understand" | "code" | "check";

export function sceneBlocks(
  content: Pick<LessonContent, "scenes"> | undefined,
  scene: Scene,
): Block[] {
  return content?.scenes[scene]?.blocks ?? [];
}

export function blocksOfType<T extends Block["type"]>(
  blocks: readonly Block[],
  type: T,
): BlockOf<T>[] {
  return blocks.filter((block): block is BlockOf<T> => block.type === type);
}

/** What the current lesson page renders, read from content v2. */
export function lessonView(content: LessonContent | undefined) {
  const understand = sceneBlocks(content, "understand");
  const check = sceneBlocks(content, "check");
  const observe: ObservePoint[] =
    content?.scenes.lab?.experiments.flatMap((item) => item.observe) ?? [];
  const quiz: QuizQuestion[] = blocksOfType(check, "quiz").flatMap(
    (block) => block.questions,
  );
  return {
    hero: blocksOfType(understand, "hero")[0],
    concepts: blocksOfType(understand, "concepts").flatMap(
      (block) => block.items,
    ),
    sections: blocksOfType(understand, "prose"),
    walkthrough: blocksOfType(understand, "walkthrough")[0],
    observe,
    quiz,
  };
}

const sectionKinds = {
  prose: "explanation",
  steps: "steps",
  compare: "comparison",
  callout: "warning",
} as const;

/** What the current onboarding page renders for one v2 chapter. */
export function chapterView(chapter: Chapter) {
  const understand = sceneBlocks(chapter, "understand");
  const exercise = blocksOfType(sceneBlocks(chapter, "check"), "checkpoint")[0];
  const sections = understand.flatMap((block) => {
    if (!(block.type in sectionKinds)) return [];
    const section = block as BlockOf<keyof typeof sectionKinds>;
    return [
      {
        id: section.id,
        kind: sectionKinds[section.type],
        title: section.title ?? "",
        paragraphs: section.paragraphs,
        bullets:
          section.type === "steps"
            ? section.items.map((item) => item.text)
            : [],
        table:
          section.type === "compare"
            ? { columns: section.columns, rows: section.rows }
            : undefined,
      },
    ];
  });
  return {
    objectives: blocksOfType(understand, "objectives").flatMap((block) =>
      block.items.map((item) => item.text),
    ),
    sections,
    references: blocksOfType(understand, "references").flatMap(
      (block) => block.items,
    ),
    exercise: {
      title: exercise?.title ?? "",
      prompt: exercise?.prompt ?? "",
      checkpoints: exercise?.items ?? [],
    },
  };
}
