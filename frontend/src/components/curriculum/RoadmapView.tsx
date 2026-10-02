/**
 * Zoomable prerequisite roadmap (@xyflow/react + elkjs). Lazy-loaded: the
 * course map only pulls this chunk when the learner opens the route view on a
 * wide screen. Nodes are plain buttons with a roving tabindex; arrow keys move
 * spatially between lessons, Enter opens an available lesson, and a planned
 * lesson only shows its plan. This file only assembles the parts in
 * `roadmap/` (layout, elements, focus, entrance, node and detail).
 */
import { useMemo, useRef } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useTranslation } from "react-i18next";
import { LoaderCircle } from "lucide-react";
import { formatLessonNumber } from "../../lib/lessonIds";
import type { ProgressRecord } from "../../progress";
import type { CurriculumLesson } from "../../types";
import { lessonMarks, type CurriculumGraph } from "./graph";
import { NODE_HEIGHT } from "./layout";
import { LessonNode } from "./roadmap/LessonNode";
import {
  NodeControlsContext,
  type LessonFlowNode,
} from "./roadmap/nodeControls";
import { RoadmapDetail } from "./roadmap/RoadmapDetail";
import { useRoadmapElements } from "./roadmap/useRoadmapElements";
import { useRoadmapEntrance } from "./roadmap/useRoadmapEntrance";
import { useRoadmapFocus } from "./roadmap/useRoadmapFocus";
import { useRoadmapLayout } from "./roadmap/useRoadmapLayout";

export interface RoadmapViewProps {
  graph: CurriculumGraph;
  lessons: CurriculumLesson[];
  progress: ProgressRecord;
  /** Lessons matching the current filters; others are dimmed, not removed. */
  matches: ReadonlySet<string>;
  onSelectLesson: (id: string) => void;
}

const nodeTypes = { lesson: LessonNode };

function RoadmapCanvas({
  graph,
  lessons,
  progress,
  matches,
  onSelectLesson,
}: RoadmapViewProps) {
  const { t } = useTranslation("curriculum");
  const containerRef = useRef<HTMLDivElement>(null);
  // Edge current and node entrances run only on screen in a visible tab.
  const { ref: flowRef, flowActive, entered } = useRoadmapEntrance();
  const { positions, error, centers } = useRoadmapLayout(graph);
  const lessonById = useMemo(
    () => new Map(lessons.map((lesson) => [lesson.id, lesson])),
    [lessons],
  );
  const { focusedId, statusOf, controls } = useRoadmapFocus({
    graph,
    lessons,
    progress,
    positions,
    centers,
    containerRef,
    onSelectLesson,
  });
  const { nodes, edges } = useRoadmapElements({
    graph,
    positions,
    progress,
    lessonById,
    matches,
    statusOf,
    focusedId,
  });

  const focusedNode = graph.nodes.find((node) => node.id === focusedId);
  const focusedLesson = focusedId ? lessonById.get(focusedId) : undefined;
  const titleOf = (id: string) => {
    const lesson = lessonById.get(id);
    return lesson ? `${formatLessonNumber(lesson.number)} ${lesson.title}` : id;
  };

  if (error)
    return (
      <div className="alert" role="alert">
        {t("roadmap.failed", { reason: error })}
      </div>
    );

  return (
    <NodeControlsContext.Provider value={controls}>
      <div
        ref={flowRef}
        className="roadmap-flow-stage"
        data-flow={flowActive}
        data-entered={entered}
      >
        <div
          ref={containerRef}
          className="roadmap-canvas"
          data-testid="curriculum-roadmap"
          role="group"
          aria-label={t("roadmap.label")}
          aria-busy={!positions}
        >
          {positions ? (
            <ReactFlow<LessonFlowNode>
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onInit={(instance) => {
                // Start readable: the focused lesson at the left edge, vertically centred.
                const box = containerRef.current?.getBoundingClientRect();
                const start = focusedId ? positions.get(focusedId) : undefined;
                if (!box || !start) {
                  void instance.fitView({ padding: 0.12 });
                  return;
                }
                const zoom = 0.9;
                void instance.setViewport({
                  x: 32 - start.x * zoom,
                  y: box.height / 2 - (start.y + NODE_HEIGHT / 2) * zoom,
                  zoom,
                });
              }}
              fitViewOptions={{ padding: 0.08 }}
              minZoom={0.1}
              maxZoom={1.6}
              nodesDraggable={false}
              nodesConnectable={false}
              nodesFocusable={false}
              edgesFocusable={false}
              elementsSelectable={false}
              disableKeyboardA11y
              zoomOnScroll={false}
              zoomOnDoubleClick={false}
              preventScrolling={false}
              panOnScroll={false}
            >
              <Background gap={24} size={1} />
              <Controls showInteractive={false} position="bottom-right" />
            </ReactFlow>
          ) : (
            <p className="roadmap-loading" role="status">
              <LoaderCircle size={18} className="spin" aria-hidden="true" />
              {t("roadmap.loading")}
            </p>
          )}
        </div>
      </div>
      {focusedLesson && focusedNode && (
        <RoadmapDetail
          key={focusedLesson.id}
          lesson={focusedLesson}
          node={focusedNode}
          marks={lessonMarks(progress, focusedLesson)}
          titleOf={titleOf}
          onSelectLesson={onSelectLesson}
        />
      )}
    </NodeControlsContext.Provider>
  );
}

export default function RoadmapView(props: RoadmapViewProps) {
  return (
    <ReactFlowProvider>
      <RoadmapCanvas {...props} />
    </ReactFlowProvider>
  );
}
