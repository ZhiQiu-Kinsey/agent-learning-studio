import { useCallback, useRef, useState, type ComponentType } from "react";
import { AnimatePresence, motion, useScroll, useTransform } from "motion/react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../motion";
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
  if (reduced) return <h1 className="band-title">{text}</h1>;
  return (
    <h1 className="band-title" data-effect={stroke ? "stroke" : "rise"}>
      <span className="sr-only">{text}</span>
      {stroke ? (
        <StrokeText
          text={text}
          className="band-title-stroke"
          strokeColor="#c8b5ff"
          fillColor="currentColor"
          onOverflow={overflow}
        />
      ) : (
        <RiseTokens text={text} />
      )}
    </h1>
  );
}

/**
 * Lesson hero band: living backdrop for the lesson's domain, glowing lesson
 * badge, entrance title, glass capability chips and the floating scene dock.
 * Always dark; scroll parallax only at full motion.
 */
export function LessonMasthead({
  lessonId,
  number,
  title,
  capabilities,
  category,
  categoryTitle,
  scene,
  icons,
  running,
  visible,
}: {
  lessonId: string;
  number: string;
  title: string;
  capabilities: LessonContent["capabilities"];
  category?: string;
  categoryTitle?: string;
  scene: SceneId;
  icons: Record<
    SceneId,
    ComponentType<{ size?: number; "aria-hidden"?: boolean | "true" }>
  >;
  running: boolean;
  visible: boolean;
}) {
  const { t } = useTranslation("lesson");
  const reduced = useReducedMotion();
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const layerY = useTransform(scrollYProgress, [0, 1], [0, 90]);
  const layerScale = useTransform(scrollYProgress, [0, 1], [1, 1.08]);
  const bodyY = useTransform(scrollYProgress, [0, 1], [0, 40]);
  const bodyOpacity = useTransform(scrollYProgress, [0, 0.85], [1, 0.2]);
  const index = sceneIds.indexOf(scene);

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
        <div className="lesson-heading">
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
          <div className="band-copy">
            <p className="masthead-kicker">
              <ShinyText
                text={t("kicker", { number })}
                color="#b7b0e8"
                shineColor="#ffffff"
                speed={2.6}
                delay={2.4}
                className="band-kicker-text"
              />
              {categoryTitle && (
                <span className="band-category">{categoryTitle}</span>
              )}
            </p>
            <BandTitle key={`${lessonId}-${title}`} text={title} />
            {capabilities.length > 0 && (
              <ul
                className="lesson-capabilities band-chips"
                aria-label={t("capabilities.region")}
                key={`chips-${lessonId}`}
              >
                {capabilities.map((capability, chip) => (
                  <motion.li
                    key={capability}
                    data-capability={capability}
                    initial={
                      reduced
                        ? false
                        : { opacity: 0, y: 12, scale: 0.9, filter: "blur(6px)" }
                    }
                    animate={{
                      opacity: 1,
                      y: 0,
                      scale: 1,
                      filter: "blur(0px)",
                    }}
                    transition={{
                      delay: 0.45 + chip * 0.08,
                      duration: 0.55,
                      ease,
                    }}
                  >
                    {t(`capabilities.${capability}`)}
                  </motion.li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="band-scene-meta" aria-hidden="true">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={scene}
              initial={
                reduced ? false : { opacity: 0, y: 10, filter: "blur(8px)" }
              }
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={
                reduced ? undefined : { opacity: 0, y: -8, filter: "blur(8px)" }
              }
              transition={{ duration: 0.32, ease }}
            >
              <span className="band-scene-index">
                {String(index + 1).padStart(2, "0")}
                <small>/{String(sceneIds.length).padStart(2, "0")}</small>
              </span>
              <span className="band-scene-hint">{t(`sceneHint.${scene}`)}</span>
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.div>

      <div className="band-dock">
        <TabsList
          className="mode-navigation scene-navigation"
          aria-label={t("scenes.region")}
          data-testid="scene-tabs"
        >
          {sceneIds.map((id) => {
            const Icon = icons[id];
            return (
              <TabsTrigger
                key={id}
                value={id}
                data-testid={`scene-tab-${id}`}
                title={t(`sceneHint.${id}`)}
              >
                {scene === id && (
                  <motion.span
                    aria-hidden="true"
                    className="mode-active-pill"
                    layoutId="lesson-scene"
                    transition={{
                      type: "spring",
                      bounce: 0.25,
                      duration: reduced ? 0 : 0.5,
                    }}
                  />
                )}
                <Icon size={16} aria-hidden="true" />
                <span className="band-tab-label">{t(`scenes.${id}`)}</span>
                {id === "lab" && running && (
                  <span className="live-indicator band-live">
                    <i aria-hidden="true" />
                    <span>{t("live")}</span>
                  </span>
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>
      </div>
    </header>
  );
}
