import type { PointerEvent } from "react";
import { useTranslation } from "react-i18next";
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
import { lessonView } from "../../content/view";
import { prefersReducedMotionNow, useMotionBudget } from "../../motion";

/** Pointer-following spotlight (SpotlightCard style) driven by CSS variables. */
const trackPointer = (event: PointerEvent<HTMLElement>) => {
  const box = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty(
    "--mx",
    `${event.clientX - box.left}px`,
  );
  event.currentTarget.style.setProperty("--my", `${event.clientY - box.top}px`);
};

export function LessonHero({
  detail,
  onSource,
}: {
  detail: Detail;
  onSource: () => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "hero" });
  const view = lessonView(detail.learning);
  const presentation = view.hero;
  const { ref, active } = useMotionBudget<HTMLElement>();
  if (!presentation)
    return (
      <div className="reading-intro">
        <span className="reading-eyebrow">{t("tagline")}</span>
        <p>{detail.description}</p>
      </div>
    );
  return (
    <section
      ref={ref}
      className={`lesson-hero ${active ? "is-animating" : ""}`}
      data-testid="lesson-hero"
      aria-label={t("region")}
      onPointerMove={active ? trackPointer : undefined}
    >
      <span className="lesson-hero-spotlight" aria-hidden="true" />
      <div className="lesson-hero-copy">
        <div className="lesson-hero-eyebrow">
          <span className="lesson-hero-dot" />
          <DecryptedText text={presentation.eyebrow} />
        </div>
        <h2>
          <BlurText text={presentation.headline} />
          <br />
          {presentation.highlight && (
            <GradientText
              colors={["#7562e9", "#b98aff", "#49dec6", "#7562e9"]}
              animationSpeed={7}
            >
              {presentation.highlight}
            </GradientText>
          )}
        </h2>
        <p className="lesson-hero-description">{detail.description}</p>
        <div className="lesson-hero-actions">
          <Magnet>
            <button
              className="lesson-hero-explore"
              onClick={() =>
                document.getElementById("lesson-flow")?.scrollIntoView({
                  behavior: prefersReducedMotionNow() ? "instant" : "smooth",
                  block: "start",
                })
              }
            >
              {t("explore")}
              <ArrowDown size={16} />
            </button>
          </Magnet>
          <button className="lesson-hero-source" onClick={onSource}>
            {t("source")}
            <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="lesson-hero-meta">
          <span>
            <Sparkles size={13} />
            {t("tagline")}
          </span>
          <span>{t("concepts", { count: view.sections.length })}</span>
        </div>
      </div>
      <div className="lesson-orbit" aria-hidden="true">
        <div className="lesson-orbit-grid" />
        <div className="lesson-orbit-ring lesson-orbit-ring-outer" />
        <div className="lesson-orbit-ring lesson-orbit-ring-inner" />
        <div className="lesson-orbit-sweep">
          <i />
        </div>
        <div className="lesson-orbit-sweep lesson-orbit-sweep-outer">
          <i />
        </div>
        <div className="lesson-orbit-core">
          <Cpu size={32} strokeWidth={1.25} />
          <strong>Agent</strong>
          <span>{t("orbit.core")}</span>
        </div>
        <div className="lesson-orbit-node orbit-node-tools">
          <Braces size={17} />
          <span>
            {t("orbit.tools")}
            <small>{t("orbit.toolsHint")}</small>
          </span>
        </div>
        <div className="lesson-orbit-node orbit-node-context">
          <Network size={17} />
          <span>
            {t("orbit.context")}
            <small>{t("orbit.contextHint")}</small>
          </span>
        </div>
        <div className="lesson-orbit-caption">
          <span />
          {t("orbit.caption")}
        </div>
      </div>
    </section>
  );
}
