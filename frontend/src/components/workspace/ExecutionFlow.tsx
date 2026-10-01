import { motion } from "motion/react";
import { useReducedMotion } from "../../motion";
import {
  ArrowRight,
  BrainCircuit,
  MessageSquare,
  Terminal,
  WandSparkles,
  Workflow,
} from "lucide-react";
import type { Trace } from "../../types";
import StatusMark from "../react-bits/StatusMark";
import CallChip from "../react-bits/CallChip";

const agentPhases = [
  { label: "任务输入", icon: MessageSquare, types: ["run_start"] },
  { label: "模型决策", icon: BrainCircuit, types: ["request", "response"] },
  { label: "工具执行", icon: Terminal, types: ["tool_call", "tool_result"] },
  { label: "组织回答", icon: WandSparkles, types: ["answer"] },
];

/** Every phase and chip is derived from the visible trace, including replay. */
export function ExecutionFlow({
  events,
  running,
  active,
  onSelect,
  requiresModel = true,
  customRuntime = false,
}: {
  events: Trace[];
  running: boolean;
  active: boolean;
  onSelect: (index: number) => void;
  requiresModel?: boolean;
  customRuntime?: boolean;
}) {
  const reduced = useReducedMotion();
  const phases =
    requiresModel && !customRuntime
      ? agentPhases
      : [
          agentPhases[0],
          {
            label: "课程步骤",
            icon: Workflow,
            types: [
              "request",
              "response",
              "tool_call",
              "tool_result",
              ...events
                .filter((event) => event.type.startsWith("lesson."))
                .map((event) => event.type),
            ],
          },
          { label: "课程输出", icon: WandSparkles, types: ["answer"] },
        ];
  const latest = events.at(-1);
  const phaseIndex = phases.findIndex((phase) =>
    phase.types.includes(latest?.type || ""),
  );
  const results = events
    .map((event, index) => ({ event, index }))
    .filter(({ event }) => event.type === "tool_result")
    .slice(-3);
  return (
    <section className="execution-flow" aria-label="实时消息流">
      <div className="execution-flow-heading">
        <span>FOLLOW THE SIGNAL</span>
        <small>
          {events.length
            ? "点击节点，查看运行证据"
            : "运行后，沿消息流观察每一步"}
        </small>
      </div>
      <div className="execution-nodes">
        {phases.map((phase, index) => {
          const eventIndex = events.findLastIndex((event) =>
            phase.types.includes(event.type),
          );
          const current = running && phaseIndex === index;
          const failed =
            eventIndex >= 0 &&
            events[eventIndex].type === "tool_result" &&
            (events[eventIndex].data.result as { ok?: boolean })?.ok === false;
          const Icon = phase.icon;
          return (
            <div className="execution-node-group" key={phase.label}>
              {index > 0 && (
                <ArrowRight
                  className={
                    eventIndex >= 0 ? "flow-arrow reached" : "flow-arrow"
                  }
                  size={16}
                  aria-hidden="true"
                />
              )}
              <motion.button
                type="button"
                className={`execution-node ${current ? "is-current" : ""} ${eventIndex >= 0 ? "is-reached" : ""}`}
                disabled={eventIndex < 0}
                onClick={() => onSelect(eventIndex)}
                whileHover={reduced ? {} : { y: -3 }}
                whileTap={reduced ? {} : { scale: 0.97 }}
                aria-label={`查看${phase.label}事件`}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{phase.label}</span>
                <span aria-hidden="true">
                  <StatusMark
                    status={
                      failed
                        ? "failed"
                        : current && active
                          ? "running"
                          : eventIndex >= 0
                            ? "done"
                            : "pending"
                    }
                    size={14}
                    strike={false}
                    doneColor="var(--success)"
                    errorColor="var(--danger)"
                  />
                </span>
              </motion.button>
            </div>
          );
        })}
      </div>
      {!!results.length && (
        <div className="execution-tools" aria-label="最近工具结果">
          {results.map(({ event, index }) => {
            const result = event.data.result as { ok?: boolean } | undefined;
            const failed = result?.ok === false;
            const name = String(event.data.name || "Python 工具");
            return (
              <button
                key={index}
                type="button"
                onClick={() => onSelect(index)}
                aria-label={`查看 ${name} ${failed ? "失败" : "完成"}结果`}
              >
                <CallChip
                  name={name}
                  argument={failed ? "执行失败" : "执行完成"}
                  status={failed ? "error" : "done"}
                  showTimer={false}
                  size={29}
                  surfaceColor="var(--surface)"
                  doneColor="var(--success)"
                  errorColor="var(--danger)"
                  shake={reduced ? 0 : 3}
                />
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
