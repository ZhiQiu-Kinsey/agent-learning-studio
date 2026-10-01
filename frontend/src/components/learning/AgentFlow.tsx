import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useMotionPreference as useReducedMotion } from "../../hooks/useMotionPreference";
import {
  ArrowLeft,
  ArrowRight,
  CheckCheck,
  Code2,
  CornerDownRight,
  Info,
} from "lucide-react";
import type { LearningPresentation } from "../../types";
import { Code } from "../Code";

export function AgentFlow({ flow }: { flow: LearningPresentation["flow"] }) {
  const [selected, setSelected] = useState(0);
  const reduced = useReducedMotion();
  const step = flow.steps[selected];
  if (!step) return null;
  return (
    <section
      className="agent-flow"
      id="lesson-flow"
      aria-label="Agent 调用过程教学示意"
    >
      <div className="learn-section-kicker">
        <span>01 / EXPLORE THE LOOP</span>
        <span className="lesson-example-tag">
          <Info size={12} />
          教学示意
        </span>
      </div>
      <div className="agent-flow-heading">
        <h2>{flow.title}</h2>
        <p>{flow.description}</p>
      </div>
      <div className="agent-flow-steps" aria-label="选择调用过程步骤">
        {flow.steps.map((item, index) => (
          <button
            key={item.label}
            className={`agent-flow-step ${index === selected ? "is-selected" : ""} ${index < selected ? "is-visited" : ""}`}
            onClick={() => setSelected(index)}
            aria-pressed={index === selected}
            aria-controls="agent-flow-detail"
          >
            <span className="agent-step-number">
              {index < selected ? <CheckCheck size={14} /> : `0${index + 1}`}
            </span>
            <span>
              <strong>{item.label}</strong>
              <small>{item.actor}</small>
            </span>
            {index < flow.steps.length - 1 && (
              <ArrowRight
                className="agent-step-connector"
                size={14}
                aria-hidden="true"
              />
            )}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={selected}
          id="agent-flow-detail"
          className="agent-flow-detail"
          aria-live="polite"
          initial={reduced ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? undefined : { opacity: 0, y: -5 }}
          transition={{ duration: 0.16 }}
        >
          <div className="agent-flow-explanation">
            <span className="agent-flow-actor">
              <CornerDownRight size={15} />
              {step.actor}
            </span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
            <div className="agent-flow-evidence">
              <EyeIcon />
              <div>
                <strong>你要核对的证据</strong>
                <p>{step.evidence}</p>
              </div>
            </div>
          </div>
          <div className="agent-flow-code">
            <div className="agent-code-toolbar">
              <span>
                <Code2 size={13} />
                {step.language === "python" ? "Python" : "消息结构"}
              </span>
              <span>示意片段 · 非运行记录</span>
            </div>
            <Code content={step.code} language={step.language} />
          </div>
        </motion.div>
      </AnimatePresence>
      <div className="agent-flow-footer">
        <p>点击上方步骤，沿着数据流读懂一次调用。</p>
        <div>
          <span>
            {String(selected + 1).padStart(2, "0")}
            <i> / {String(flow.steps.length).padStart(2, "0")}</i>
          </span>
          <button
            aria-label="上一个示意步骤"
            disabled={selected === 0}
            onClick={() => setSelected(selected - 1)}
          >
            <ArrowLeft size={15} />
          </button>
          <button
            aria-label="下一个示意步骤"
            disabled={selected === flow.steps.length - 1}
            onClick={() => setSelected(selected + 1)}
          >
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </section>
  );
}

function EyeIcon() {
  return (
    <span className="agent-evidence-icon">
      <CheckCheck size={17} />
    </span>
  );
}
