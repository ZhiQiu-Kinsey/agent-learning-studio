import { lazy, Suspense, useEffect, useState, type ComponentType } from "react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  Code2,
  FlaskConical,
  ListChecks,
  NotebookPen,
} from "lucide-react";
import { MotionIntent, useReducedMotion } from "../motion";
import { formatLessonNumber } from "../lib/lessonIds";
import { track } from "../progress";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import type { StudioState } from "../hooks/useStudio";
import { sceneIds, type SceneId, type SceneProps } from "./types";
import "../styles/scenes.css";

const scenes: Record<SceneId, ComponentType<SceneProps>> = {
  understand: lazy(() =>
    import("./UnderstandScene").then((m) => ({ default: m.UnderstandScene })),
  ),
  code: lazy(() =>
    import("./CodeScene").then((m) => ({ default: m.CodeScene })),
  ),
  lab: lazy(() => import("./LabScene").then((m) => ({ default: m.LabScene }))),
  check: lazy(() =>
    import("./CheckScene").then((m) => ({ default: m.CheckScene })),
  ),
  review: lazy(() =>
    import("./ReviewScene").then((m) => ({ default: m.ReviewScene })),
  ),
};
const icons = {
  understand: BookOpen,
  code: Code2,
  lab: FlaskConical,
  check: ListChecks,
  review: NotebookPen,
};

/** Other parts of the app (command palette, CTAs) can ask for a scene. */
export const SCENE_EVENT = "agent-lab:scene";
export function requestScene(scene: SceneId) {
  window.dispatchEvent(
    new CustomEvent<SceneId>(SCENE_EVENT, { detail: scene }),
  );
}

export function LessonScenes({
  studio,
  visible,
  onConfigure,
}: {
  studio: StudioState;
  /** False while the curriculum map or onboarding covers the lesson page. */
  visible: boolean;
  onConfigure: () => void;
}) {
  const { t } = useTranslation("lesson");
  const reduced = useReducedMotion();
  const [scene, setScene] = useState<SceneId>("understand");
  const [opened, setOpened] = useState<Set<SceneId>>(
    () => new Set(["understand"]),
  );
  const detail = studio.detail;
  const lessonId = detail?.id;

  const goTo = (next: SceneId) => {
    setScene(next);
    setOpened((previous) =>
      previous.has(next) ? previous : new Set(previous).add(next),
    );
    window.scrollTo({ top: 0, behavior: reduced ? "instant" : "smooth" });
  };

  useEffect(() => {
    const listener = (event: Event) =>
      goTo((event as CustomEvent<SceneId>).detail);
    window.addEventListener(SCENE_EVENT, listener);
    return () => window.removeEventListener(SCENE_EVENT, listener);
  });

  useEffect(() => {
    if (lessonId && visible) track.sceneVisited(lessonId, scene);
  }, [lessonId, scene, visible]);

  // A newly chosen lesson starts at 理解.
  useEffect(() => {
    setScene("understand");
  }, [lessonId]);

  // A running lab keeps the learner informed even from other scenes.
  useEffect(() => {
    if (studio.running) goTo("lab");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studio.running]);

  if (studio.lessonError)
    return (
      <div className="learn-empty" role="alert">
        {studio.lessonError}
      </div>
    );
  if (!detail)
    return (
      <div className="learn-empty" role="status">
        {t("loading")}
      </div>
    );

  const title = detail.title.replace(/^第\s*\d+\s*课[：:]?\s*/, "");
  const number = formatLessonNumber(detail.number);
  const capabilities = detail.learning?.capabilities ?? [];
  return (
    <Tabs
      value={scene}
      onValueChange={(value) => goTo(value as SceneId)}
      className="workspace-modes lesson-scenes"
    >
      <div className="lesson-masthead" data-testid="lesson-masthead">
        <div className="masthead-aurora" aria-hidden="true">
          {visible && (
            <MotionIntent
              name="ambient.aurora"
              colorStops={["#6d5dfc", "#49dec6", "#b98aff"]}
              amplitude={0.65}
              blend={0.65}
              speed={0.55}
            />
          )}
        </div>
        <div className="lesson-heading">
          <span className="lesson-badge" data-testid="lesson-badge">
            {number}
          </span>
          <div>
            <p className="masthead-kicker">{t("kicker", { number })}</p>
            <MotionIntent
              name="heading.split"
              key={`${detail.id}-${title}`}
              text={title}
              tag="h1"
              textAlign="left"
              splitType="chars"
              delay={45}
              duration={0.55}
              from={{ opacity: 0, y: 14, rotateX: -25 }}
              to={{ opacity: 1, y: 0, rotateX: 0 }}
              rootMargin="0px"
            />
            {capabilities.length > 0 && (
              <ul
                className="lesson-capabilities"
                aria-label={t("capabilities.region")}
              >
                {capabilities.map((capability) => (
                  <li key={capability} data-capability={capability}>
                    {t(`capabilities.${capability}`)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
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
                      bounce: 0.15,
                      duration: reduced ? 0 : 0.4,
                    }}
                  />
                )}
                <Icon size={16} aria-hidden="true" />
                {t(`scenes.${id}`)}
                {id === "lab" && studio.running && (
                  <i className="live-indicator" />
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>
      </div>
      {sceneIds.map((id) => {
        const Scene = scenes[id];
        return (
          <TabsContent
            key={id}
            value={id}
            forceMount
            hidden={scene !== id}
            className="mode-panel scene-panel motion-safe:animate-in motion-safe:fade-in motion-safe:duration-200"
          >
            {opened.has(id) && (
              <Suspense
                fallback={
                  <div className="learn-empty" role="status">
                    {t("loading")}
                  </div>
                }
              >
                <Scene
                  studio={studio}
                  active={visible && scene === id}
                  goTo={goTo}
                  onConfigure={onConfigure}
                />
              </Suspense>
            )}
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
