import type { ReactNode } from "react";
import type { StudioState } from "../hooks/useStudio";

/** Extensions use the shared lifecycle, event stream and replay state. */
export type LessonExtensionProps = {
  studio: StudioState;
  active: boolean;
  /** Render this to compose with the platform's default view. */
  children: ReactNode;
};

export type GuideExtensionProps = LessonExtensionProps & {
  onStartLab: () => void;
};

export type LabExtensionProps = LessonExtensionProps & {
  onConfigure: () => void;
};

export type InspectorExtensionProps = LessonExtensionProps;

export type LessonExtensionSlots = {
  guide: GuideExtensionProps;
  lab: LabExtensionProps;
  inspector: InspectorExtensionProps;
};
