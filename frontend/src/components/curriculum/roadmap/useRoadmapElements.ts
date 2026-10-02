import { useMemo } from "react";
import { MarkerType, type Edge } from "@xyflow/react";
import type { ProgressRecord } from "../../../progress";
import type { CurriculumLesson } from "../../../types";
import { lessonMarks, type CurriculumGraph } from "../graph";
import { NODE_HEIGHT, NODE_WIDTH, type Positions } from "../layout";
import type { LessonFlowNode } from "./nodeControls";

/** Entrance stagger per layout column, capped so wide graphs settle quickly. */
const COLUMN_BEAT = 90;
const MAX_DELAY = 1100;

/**
 * React Flow nodes and edges for the laid-out graph. Nodes carry their marks,
 * filter dimming and entrance delay; edges are classed by whether both ends
 * are available (flowing current) and whether they touch the focused lesson.
 */
export function useRoadmapElements({
  graph,
  positions,
  progress,
  lessonById,
  matches,
  statusOf,
  focusedId,
}: {
  graph: CurriculumGraph;
  positions: Positions | null;
  progress: ProgressRecord;
  lessonById: Map<string, CurriculumLesson>;
  matches: ReadonlySet<string>;
  statusOf: ReadonlyMap<string, CurriculumLesson["status"]>;
  focusedId: string | undefined;
}) {
  // Layout columns, left to right, so nodes can arrive one column at a time.
  const columnOf = useMemo(() => {
    const columns = [
      ...new Set([...(positions?.values() ?? [])].map((p) => Math.round(p.x))),
    ].sort((a, b) => a - b);
    return (x: number) => Math.max(0, columns.indexOf(Math.round(x)));
  }, [positions]);

  const nodes = useMemo<LessonFlowNode[]>(
    () =>
      positions
        ? graph.nodes.map((node) => ({
            id: node.id,
            type: "lesson",
            position: positions.get(node.id) ?? { x: 0, y: 0 },
            width: NODE_WIDTH,
            height: NODE_HEIGHT,
            draggable: false,
            selectable: false,
            focusable: false,
            data: {
              node,
              marks: lessonMarks(progress, lessonById.get(node.id) ?? node),
              dimmed: !matches.has(node.id),
              enterDelay: Math.min(
                columnOf(positions.get(node.id)?.x ?? 0) * COLUMN_BEAT,
                MAX_DELAY,
              ),
            },
          }))
        : [],
    [positions, graph, progress, lessonById, matches, columnOf],
  );

  const edges = useMemo<Edge[]>(
    () =>
      graph.edges.map((edge) => {
        const open =
          statusOf.get(edge.source) === "available" &&
          statusOf.get(edge.target) === "available";
        // Prerequisite links of the lesson in focus light up.
        const linked = edge.source === focusedId || edge.target === focusedId;
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: "smoothstep",
          focusable: false,
          selectable: false,
          zIndex: linked ? 1 : 0,
          className: `${open ? "is-available" : "is-planned"}${linked ? " is-linked" : ""}`,
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
        };
      }),
    [graph, statusOf, focusedId],
  );

  return { nodes, edges };
}
