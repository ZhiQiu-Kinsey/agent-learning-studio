import { createContext, type KeyboardEvent } from "react";
import type { Node } from "@xyflow/react";
import type { Direction, LessonMarks, RoadmapNode } from "../graph";

export type LessonNodeData = {
  node: RoadmapNode;
  marks: LessonMarks;
  dimmed: boolean;
  /** Entrance stagger: one beat per layout column, left to right. */
  enterDelay: number;
};
export type LessonFlowNode = Node<LessonNodeData, "lesson">;

/** What a node button needs from the canvas: roving focus and activation. */
export interface NodeControls {
  focusedId: string | undefined;
  onActivate: (id: string) => void;
  onFocusNode: (id: string) => void;
  onKeyDown: (id: string, event: KeyboardEvent<HTMLButtonElement>) => void;
}
export const NodeControlsContext = createContext<NodeControls | null>(null);

export const keyDirections: Record<string, Direction> = {
  ArrowLeft: "left",
  ArrowRight: "right",
  ArrowUp: "up",
  ArrowDown: "down",
};
