import {
  ArrowDown,
  ArrowUpRight,
  Braces,
  Cpu,
  Network,
  Sparkles,
} from "lucide-react";
import type { Detail } from "../../types";
import BlurText from "../react-bits/BlurText";
import GradientText from "../react-bits/GradientText";
import DecryptedText from "../react-bits/DecryptedText";
import Magnet from "../react-bits/Magnet";
import { prefersReducedMotionNow, useMotionBudget } from "../../motion";

export function LessonHero({
  detail,
  onSource,
}: {
  detail: Detail;
  onSource: () => void;
}) {
  const presentation = detail.learning?.presentation;
  const { ref, active } = useMotionBudget<HTMLElement>();
  if (!presentation)
    return (
      <div className="reading-intro">
        <span className="reading-eyebrow">理解原理，再动手验证</span>
        <p>{detail.description}</p>
      </div>
    );
  return (
    <section
      ref={ref}
      className={`lesson-hero ${active ? "is-animating" : ""}`}
      aria-label="本课导读概览"
    >
      <div className="lesson-hero-copy">
        <div className="lesson-hero-eyebrow">
          <span className="lesson-hero-dot" />
          <DecryptedText text={presentation.eyebrow} />
        </div>
        <h2>
          <BlurText text={presentation.headline} />
          <br />
          <GradientText>{presentation.highlight}</GradientText>
        </h2>
        <p className="lesson-hero-description">{detail.description}</p>
        <div className="lesson-hero-actions">
          <Magnet>
            <button
              className="lesson-hero-explore"
              onClick={() =>
                document
                  .getElementById("lesson-flow")
                  ?.scrollIntoView({
                    behavior: prefersReducedMotionNow() ? "instant" : "smooth",
                    block: "start",
                  })
              }
            >
              探索调用过程
              <ArrowDown size={16} />
            </button>
          </Magnet>
          <button className="lesson-hero-source" onClick={onSource}>
            对照本课源码
            <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="lesson-hero-meta">
          <span>
            <Sparkles size={13} />
            理解原理，再动手验证
          </span>
          <span>{detail.learning?.sections.length ?? 0} 个核心概念</span>
        </div>
      </div>
      <div className="lesson-orbit" aria-hidden="true">
        <div className="lesson-orbit-grid" />
        <div className="lesson-orbit-ring lesson-orbit-ring-outer" />
        <div className="lesson-orbit-ring lesson-orbit-ring-inner" />
        <div className="lesson-orbit-sweep">
          <i />
        </div>
        <div className="lesson-orbit-core">
          <Cpu size={32} strokeWidth={1.25} />
          <strong>Agent</strong>
          <span>感知 · 决策 · 行动</span>
        </div>
        <div className="lesson-orbit-node orbit-node-tools">
          <Braces size={17} />
          <span>
            Python 工具<small>执行与校验</small>
          </span>
        </div>
        <div className="lesson-orbit-node orbit-node-context">
          <Network size={17} />
          <span>
            消息历史<small>观察与上下文</small>
          </span>
        </div>
        <div className="lesson-orbit-caption">
          <span />
          让每一步都有迹可循
        </div>
      </div>
    </section>
  );
}
