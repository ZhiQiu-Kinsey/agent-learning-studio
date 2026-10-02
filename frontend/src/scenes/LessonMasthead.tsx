import { useCallback, useRef, useState } from "react";
import { motion, useScroll, useTransform } from "motion/react";
import { ArrowUpRight, Check } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../motion";
import { useResolvedTheme } from "../hooks/useTheme";
import { Backdrop } from "../components/backdrops/Backdrop";
import { backdropFor } from "../components/backdrops/presets";
import ShinyText from "../components/react-bits/ShinyText";
import StarBorder from "../components/react-bits/StarBorder";
import StrokeText from "../components/react-bits/StrokeText";
import { TabsList, TabsTrigger } from "../components/ui/tabs";
import type { LessonContent } from "../content/types.gen";
import { sceneIds, type SceneId } from "./types";

const ease = [0.16, 1, 0.3, 1] as const;

/** Word runs stay together; CJK characters animate one by one. */
const tokens = (text: string) =>
  text.match(/[A-Za-z0-9_\-.'/+#]+|\s+|./gu) ?? [text];

/** Fallback entrance for titles too long for one stroked line: blur-rise tokens. */
function RiseTokens({ text }: { text: string }) {
  return (
    <span aria-hidden="true">
      {tokens(text).map((token, index) =>
        /^\s+$/.test(token) ? (
          <span key={index}> </span>
        ) : (
          <motion.span
            key={index}
            className="band-title-token"
            initial={{ opacity: 0, y: "0.5em", filter: "blur(12px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ delay: 0.12 + index * 0.05, duration: 0.75, ease }}
          >
            {token}
          </motion.span>
        ),
      )}
    </span>
  );
}

/**
 * h1 that draws its outline first, then fills (StrokeText). Still an h1 whose
 * accessible text is the plain title; titles wider than one line fall back to
 * the blur-rise tokens, and static motion renders plain text.
 */
function BandTitle({ text }: { text: string }) {
  const reduced = useReducedMotion();
  const [stroke, setStroke] = useState(true);
  const overflow = useCallback(() => setStroke(false), []);
  const dark = useResolvedTheme() === "dark";
  if (reduced) return <h1 className="band-title">{text}</h1>;
  return (
    <h1 className="band-title" data-effect={stroke ? "stroke" : "rise"}>
      <span className="sr-only">{text}</span>
      {stroke ? (
        <StrokeText
          text={text}
          className="band-title-stroke"
          strokeColor={dark ? "#c8b5ff" : "#6d5dfc"}
          fillColor="currentColor"
          fadeStroke
          onOverflow={overflow}
        />
      ) : (
        <RiseTokens text={text} />
      )}
    </h1>
  );
}

/**
 * Lesson masthead, shared by all five scenes: the domain backdrop, the lesson
 * number once, title, subtitle and description, the lesson's objectives, and
 * underline scene tabs with the capability chips and a way to the source.
 * Follows the theme (band tokens); scroll parallax only at full motion.
 */
export function LessonMasthead({
  lessonId,
  number,
  title,
  subtitle,
  description,
  objectives,
  capabilities,
  category,
  categoryTitle,
  moduleTitle,
  scene,
  running,
  visible,
  onSource,
}: {
  lessonId: string;
  number: string;
  title: string;
  subtitle?: string;
  description: string;
  objectives: string[];
  capabilities: LessonContent["capabilities"];
  category?: string;
  categoryTitle?: string;
  moduleTitle?: string;
  scene: SceneId;
  running: boolean;
  visible: boolean;
  onSource: () => void;
}) {
  const { t } = useTranslation("lesson");
  const reduced = useReducedMotion();
  const dark = useResolvedTheme() === "dark";
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const layerY = useTransform(scrollYProgress, [0, 1], [0, 90]);
  const layerScale = useTransform(scrollYProgress, [0, 1], [1, 1.08]);
  const bodyY = useTransform(scrollYProgress, [0, 1], [0, 30]);
  const bodyOpacity = useTransform(scrollYProgress, [0, 0.85], [1, 0.25]);
  const rise = (step: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: 10, filter: "blur(6px)" },
          animate: { opacity: 1, y: 0, filter: "blur(0px)" },
          transition: { delay: 0.3 + step * 0.08, duration: 0.55, ease },
        };

  return (
    <header
      ref={ref}
      className="lesson-masthead lesson-band"
      data-testid="lesson-masthead"
      data-category={category}
      data-running={running || undefined}
    >
      <motion.div
        className="band-layer"
        aria-hidden="true"
        style={reduced ? undefined : { y: layerY, scale: layerScale }}
      >
        {visible && (
          <Backdrop
            name={backdropFor(category)}
            className="masthead-backdrop"
          />
        )}
      </motion.div>
      <div className="band-scrim" aria-hidden="true" />
      <div className="band-texture" aria-hidden="true" />
      <div className="band-flare" aria-hidden="true" />

      <motion.div
        className="band-body"
        style={reduced ? undefined : { y: bodyY, opacity: bodyOpacity }}
      >
        <motion.div
          className="band-badge-wrap"
          key={`badge-${lessonId}`}
          initial={reduced ? false : { opacity: 0, scale: 0.6, rotate: -12 }}
          animate={{ opacity: 1, scale: 1, rotate: 0 }}
          transition={{ type: "spring", bounce: 0.45, duration: 0.9 }}
        >
          <span className="band-badge-halo" aria-hidden="true" />
          <StarBorder className="band-badge" color="#49dec6" speed="5s">
            <span className="lesson-badge" data-testid="lesson-badge">
              {number}
            </span>
          </StarBorder>
        </motion.div>
        <div className="band-copy" key={`copy-${lessonId}`}>
          <p className="masthead-kicker">
            <ShinyText
              text={t("kicker")}
              color={dark ? "#b7b0e8" : "#4b4668"}
              shineColor={dark ? "#ffffff" : "#6d5dfc"}
              speed={2.6}
              delay={2.4}
              className="band-kicker-text"
            />
            {categoryTitle && (
              <span className="band-category">{categoryTitle}</span>
            )}
            {moduleTitle && <span className="band-module">{moduleTitle}</span>}
          </p>
          <BandTitle key={`${lessonId}-${title}`} text={title} />
          {subtitle && (
            <motion.p className="band-subtitle" {...rise(0)}>
              {subtitle}
            </motion.p>
          )}
          <motion.p className="band-description" {...rise(1)}>
            {description}
          </motion.p>
        </div>
        {objectives.length > 0 && (
          <motion.aside
            className="band-goals"
            aria-label={t("objectives.eyebrow")}
            key={`goals-${lessonId}`}
            {...rise(2)}
          >
            <h2>{t("objectives.title")}</h2>
            <ul>
              {objectives.map((objective, item) => (
                <li key={item}>
                  <Check size={14} aria-hidden="true" />
                  {objective}
                </li>
              ))}
            </ul>
          </motion.aside>
        )}
      </motion.div>

      <div className="band-dock">
        <TabsList
          className="mode-navigation scene-navigation"
          aria-label={t("scenes.region")}
          data-testid="scene-tabs"
        >
          {sceneIds.map((id, index) => (
            <TabsTrigger
              key={id}
              value={id}
              data-testid={`scene-tab-${id}`}
              title={t(`sceneHint.${id}`)}
            >
              <span className="band-tab-index" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="band-tab-label">{t(`scenes.${id}`)}</span>
              {id === "lab" && running && (
                <span className="live-indicator band-live">
                  <i aria-hidden="true" />
                  <span>{t("live")}</span>
                </span>
              )}
              {scene === id && (
                <motion.span
                  aria-hidden="true"
                  className="band-tab-underline"
                  layoutId="lesson-scene"
                  transition={{
                    type: "spring",
                    bounce: 0.2,
                    duration: reduced ? 0 : 0.45,
                  }}
                />
              )}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="band-dock-side">
          {capabilities.length > 0 && (
            <ul
              className="lesson-capabilities band-chips"
              aria-label={t("capabilities.region")}
            >
              {capabilities.map((capability) => (
                <li key={capability} data-capability={capability}>
                  {t(`capabilities.${capability}`)}
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="band-source" onClick={onSource}>
            {t("source")}
            <ArrowUpRight size={15} aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  );
}
