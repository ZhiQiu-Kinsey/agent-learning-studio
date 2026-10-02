import { useContext, type CSSProperties } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useTranslation } from "react-i18next";
import { LockKeyhole } from "lucide-react";
import { formatLessonNumber } from "../../../lib/lessonIds";
import { ProgressMarks } from "../ProgressMarks";
import { NodeControlsContext, type LessonFlowNode } from "./nodeControls";

/**
 * One lesson on the canvas: a plain button with a roving tabindex. Its
 * entrance delay comes from the layout column (see roadmapElements.ts).
 */
export function LessonNode({ data }: NodeProps<LessonFlowNode>) {
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
