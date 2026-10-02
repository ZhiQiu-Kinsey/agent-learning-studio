import { useCallback, useMemo, useState, type RefObject } from "react";
import { useReactFlow } from "@xyflow/react";
import { useReducedMotion } from "../../../motion";
import type { ProgressRecord } from "../../../progress";
import type { CurriculumLesson } from "../../../types";
import { neighborInDirection, type CurriculumGraph } from "../graph";
import { NODE_HEIGHT, NODE_WIDTH, type Positions } from "../layout";
import {
  keyDirections,
  type LessonFlowNode,
  type NodeControls,
} from "./nodeControls";

type Center = { id: string; x: number; y: number };

/**
 * The lesson in focus (roving tabindex) and the node controls: arrow keys move
 * spatially, Home/End jump to the first/last lesson, activating an available
 * lesson opens it. The focused lesson drives the detail panel and the linked
 * edges, and is kept inside the viewport.
 */
export function useRoadmapFocus({
  graph,
  lessons,
  progress,
  positions,
  centers,
  containerRef,
  onSelectLesson,
}: {
  graph: CurriculumGraph;
  lessons: CurriculumLesson[];
  progress: ProgressRecord;
  positions: Positions | null;
  centers: Center[];
  containerRef: RefObject<HTMLDivElement | null>;
  onSelectLesson: (id: string) => void;
}) {
  const reduced = useReducedMotion();
  const flow = useReactFlow<LessonFlowNode>();
  const ordered = useMemo(
    () => [...graph.nodes].sort((a, b) => a.number - b.number),
    [graph],
  );
  const statusOf = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node.status])),
    [graph],
  );
  // Start where the learner last was (a real record), else the first available lesson.
  const [focusedId, setFocusedId] = useState<string | undefined>(
    () =>
      (
        ordered.find(
          (node) =>
            node.status === "available" &&
            !!progress.lastLessonId &&
            (node.id === progress.lastLessonId ||
              lessons
                .find((lesson) => lesson.id === node.id)
                ?.aliases?.includes(progress.lastLessonId)),
        ) ??
        ordered.find((node) => node.status === "available") ??
        ordered[0]
      )?.id,
  );

  const ensureVisible = useCallback(
    (id: string) => {
      const point = positions?.get(id);
      const box = containerRef.current?.getBoundingClientRect();
      if (!point || !box) return;
      const { x, y, zoom } = flow.getViewport();
      const left = point.x * zoom + x;
      const top = point.y * zoom + y;
      if (
        left < 0 ||
        top < 0 ||
        left + NODE_WIDTH * zoom > box.width ||
        top + NODE_HEIGHT * zoom > box.height
      )
        void flow.setCenter(
          point.x + NODE_WIDTH / 2,
          point.y + NODE_HEIGHT / 2,
          { zoom, duration: reduced ? 0 : 200 },
        );
    },
    [positions, flow, reduced, containerRef],
  );

  const moveFocus = useCallback(
    (id: string | undefined) => {
      if (!id) return;
      setFocusedId(id);
      ensureVisible(id);
      containerRef.current
        ?.querySelector<HTMLButtonElement>(
          `[data-testid="roadmap-node"][data-lesson-id="${CSS.escape(id)}"]`,
        )
        // The pane is transformed; let React Flow pan instead of the browser scrolling it.
        ?.focus({ preventScroll: true });
    },
    [ensureVisible, containerRef],
  );

  const controls = useMemo<NodeControls>(
    () => ({
      focusedId,
      onActivate(id) {
        setFocusedId(id);
        if (statusOf.get(id) === "available") onSelectLesson(id);
      },
      onFocusNode(id) {
        setFocusedId(id);
        ensureVisible(id);
      },
      onKeyDown(id, event) {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        const direction = keyDirections[event.key];
        let target: string | undefined;
        if (direction) target = neighborInDirection(centers, id, direction);
        else if (event.key === "Home") target = ordered[0]?.id;
        else if (event.key === "End") target = ordered[ordered.length - 1]?.id;
        else return;
        event.preventDefault();
        event.stopPropagation();
        moveFocus(target);
      },
    }),
    [
      focusedId,
      statusOf,
      onSelectLesson,
      ensureVisible,
      centers,
      ordered,
      moveFocus,
    ],
  );

  return { focusedId, statusOf, controls };
}
