/**
 * Zoomable prerequisite roadmap (@xyflow/react + elkjs). Lazy-loaded: the
 * course map only pulls this chunk when the learner opens the route view on a
 * wide screen. Nodes are plain buttons with a roving tabindex; arrow keys move
 * spatially between lessons, Enter opens an available lesson, and a planned
 * lesson only shows its plan.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { motion } from "motion/react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useTranslation } from "react-i18next";
import { ArrowRight, LoaderCircle, LockKeyhole } from "lucide-react";
import { useMotionBudget, useReducedMotion } from "../../motion";
import { formatLessonNumber } from "../../lib/lessonIds";
import type { ProgressRecord } from "../../progress";
import type { CurriculumLesson } from "../../types";
import { Button } from "../ui/button";
import {
  lessonMarks,
  neighborInDirection,
  type CurriculumGraph,
  type Direction,
  type LessonMarks,
  type RoadmapNode,
} from "./graph";
import {
  layoutRoadmap,
  NODE_HEIGHT,
  NODE_WIDTH,
  type Positions,
} from "./layout";
import { ProgressMarks } from "./ProgressMarks";

export interface RoadmapViewProps {
  graph: CurriculumGraph;
  lessons: CurriculumLesson[];
  progress: ProgressRecord;
  /** Lessons matching the current filters; others are dimmed, not removed. */
  matches: ReadonlySet<string>;
  onSelectLesson: (id: string) => void;
}

type LessonNodeData = {
  node: RoadmapNode;
  marks: LessonMarks;
  dimmed: boolean;
  /** Entrance stagger: one beat per layout column, left to right. */
  enterDelay: number;
};
type LessonFlowNode = Node<LessonNodeData, "lesson">;

interface NodeControls {
  focusedId: string | undefined;
  onActivate: (id: string) => void;
  onFocusNode: (id: string) => void;
  onKeyDown: (id: string, event: KeyboardEvent<HTMLButtonElement>) => void;
}
const NodeControlsContext = createContext<NodeControls | null>(null);

const keyDirections: Record<string, Direction> = {
  ArrowLeft: "left",
  ArrowRight: "right",
  ArrowUp: "up",
  ArrowDown: "down",
};

function LessonNode({ data }: NodeProps<LessonFlowNode>) {
  const { t } = useTranslation("curriculum");
  const controls = useContext(NodeControlsContext)!;
  const { node, marks, dimmed, enterDelay } = data;
  const status = t(`status.${node.status}`);
  return (
    <div
      className="roadmap-node"
      data-status={node.status}
      data-dimmed={dimmed}
      data-focused={controls.focusedId === node.id}
      style={{ "--enter-delay": `${enterDelay}ms` } as CSSProperties}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <button
        type="button"
        className="roadmap-node-button nodrag nopan"
        data-testid="roadmap-node"
        data-lesson-id={node.id}
        data-status={node.status}
        tabIndex={controls.focusedId === node.id ? 0 : -1}
        aria-label={`${t("roadmap.node", {
          number: node.number,
          title: node.title,
          status,
        })}${dimmed ? `, ${t("roadmap.dimmed")}` : ""}`}
        aria-describedby="roadmap-detail"
        onClick={() => controls.onActivate(node.id)}
        onFocus={() => controls.onFocusNode(node.id)}
        onKeyDown={(event) => controls.onKeyDown(node.id, event)}
      >
        <span className="roadmap-node-number" aria-hidden="true">
          {formatLessonNumber(node.number)}
        </span>
        <span className="roadmap-node-title" aria-hidden="true">
          {node.title}
        </span>
        <span className="roadmap-node-meta" aria-hidden="true">
          {node.status === "planned" && <LockKeyhole size={11} />}
          {status}
        </span>
        <ProgressMarks marks={marks} testId="roadmap-node-progress" />
      </button>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const nodeTypes = { lesson: LessonNode };

function RoadmapDetail({
  lesson,
  node,
  marks,
  titleOf,
  onSelectLesson,
}: {
  lesson: CurriculumLesson;
  node: RoadmapNode;
  marks: LessonMarks;
  titleOf: (id: string) => string;
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  return (
    <motion.div
      className="roadmap-detail"
      id="roadmap-detail"
      data-testid="roadmap-detail"
      data-lesson-id={lesson.id}
      data-status={lesson.status}
      initial={reduced ? false : { opacity: 0, y: 10, filter: "blur(6px)" }}
      animate={{
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        transitionEnd: { filter: "none" },
      }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="roadmap-detail-head">
        <small>
          {t("lessonNumber", { number: lesson.number })} ·{" "}
          {t(`status.${lesson.status}`)}
        </small>
        <strong>{lesson.title}</strong>
        <ProgressMarks marks={marks} testId="roadmap-detail-progress" />
      </div>
      <p>{lesson.summary}</p>
      <p className="roadmap-detail-prereqs">
        {node.prerequisites.length
          ? t("roadmap.prerequisites", {
              list: node.prerequisites.map(titleOf).join(t("list.separator")),
            })
          : t("roadmap.noPrerequisites")}
      </p>
      {lesson.status === "available" ? (
        <Button
          className="primary-button"
          data-testid="roadmap-detail-start"
          onClick={() => onSelectLesson(lesson.id)}
        >
          {t("roadmap.enter", { number: lesson.number })}
          <ArrowRight size={14} />
        </Button>
      ) : (
        <p
          className="curriculum-planned-note"
          data-testid="roadmap-detail-planned"
        >
          {t("roadmap.plannedNote")}
        </p>
      )}
    </motion.div>
  );
}

function RoadmapCanvas({
  graph,
  lessons,
  progress,
  matches,
  onSelectLesson,
}: RoadmapViewProps) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  const flow = useReactFlow<LessonFlowNode>();
  const containerRef = useRef<HTMLDivElement>(null);
  // Edge current and node entrances run only on screen in a visible tab.
  const { ref: flowRef, active: flowActive } =
    useMotionBudget<HTMLDivElement>("css");
  // Nodes arrive once, the first time the canvas is seen; never replayed.
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    if (flowActive) setEntered(true);
  }, [flowActive]);
  const [positions, setPositions] = useState<Positions | null>(null);
  const [error, setError] = useState("");
  const ordered = useMemo(
    () => [...graph.nodes].sort((a, b) => a.number - b.number),
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

  useEffect(() => {
    let ignore = false;
    setPositions(null);
    setError("");
    layoutRoadmap(graph)
      .then((value) => {
        if (!ignore) setPositions(value);
      })
      .catch((reason) => {
        if (!ignore)
          setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      ignore = true;
    };
  }, [graph]);

  const lessonById = useMemo(
    () => new Map(lessons.map((lesson) => [lesson.id, lesson])),
    [lessons],
  );
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
                columnOf(positions.get(node.id)?.x ?? 0) * 90,
                1100,
              ),
            },
          }))
        : [],
    [positions, graph, progress, lessonById, matches, columnOf],
  );
  const statusOf = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node.status])),
    [graph],
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
  const centers = useMemo(
    () =>
      positions
        ? [...positions].map(([id, point]) => ({
            id,
            x: point.x + NODE_WIDTH / 2,
            y: point.y + NODE_HEIGHT / 2,
          }))
        : [],
    [positions],
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
    [positions, flow, reduced],
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
    [ensureVisible],
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
              minZoom={0.25}
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
