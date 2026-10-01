import { lazy, type ComponentType } from "react";
import type { LessonExtensionSlots } from "./types";

export type ExtensionRegistry = {
  [Slot in keyof LessonExtensionSlots]: Readonly<
    Record<string, ComponentType<LessonExtensionSlots[Slot]>>
  >;
};

/** Trusted build-time imports only: never import a URL or path from lesson JSON. */
export const lessonExtensions: ExtensionRegistry = {
  guide: {},
  lab: {
    "structured-inputs": lazy(() => import("./shared/StructuredInputs")),
  },
  inspector: {
    "tool-outcomes": lazy(() => import("./lesson-03/ToolOutcomes")),
    "evidence-board": lazy(() => import("./shared/EvidenceBoard")),
  },
};
