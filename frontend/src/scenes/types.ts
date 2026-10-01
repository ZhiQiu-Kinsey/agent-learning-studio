import type { StudioState } from "../hooks/useStudio";

/** Fixed scene order of every lesson page (onboarding uses understand + check only). */
export const sceneIds = [
  "understand",
  "code",
  "lab",
  "check",
  "review",
] as const;
export type SceneId = (typeof sceneIds)[number];

/** Contract every scene component implements. */
export interface SceneProps {
  studio: StudioState;
  /** True while this scene is the visible one; pause effects otherwise. */
  active: boolean;
  goTo: (scene: SceneId) => void;
  onConfigure: () => void;
}
