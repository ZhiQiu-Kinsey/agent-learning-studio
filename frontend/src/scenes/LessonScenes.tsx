import { lazy, Suspense, useEffect, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  Code2,
  FlaskConical,
  ListChecks,
  NotebookPen,
} from "lucide-react";
import { useReducedMotion } from "../motion";
import { formatLessonNumber } from "../lib/lessonIds";
import { useCurriculum } from "../hooks/useCurriculum";
import { track } from "../progress";
import { Tabs, TabsContent } from "../components/ui/tabs";
import type { StudioState } from "../hooks/useStudio";
import { LessonMasthead } from "./LessonMasthead";
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
  const curriculum = useCurriculum();
  const category = curriculum?.lessons.find(
    (lesson) => lesson.id === lessonId,
  )?.category_id;
  const categoryTitle = curriculum?.categories.find(
    (item) => item.id === category,
  )?.title;

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

  // Recorded only when the learner actually sees the lesson page, not when it preloads.
  useEffect(() => {
    if (lessonId && visible) track.lessonOpened(lessonId);
  }, [lessonId, visible]);

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
      <LessonMasthead
        lessonId={detail.id}
        number={number}
        title={title}
        capabilities={capabilities}
        category={category}
        categoryTitle={categoryTitle}
        scene={scene}
        icons={icons}
        running={studio.running}
        visible={visible}
      />
      {sceneIds.map((id) => {
        const Scene = scenes[id];
        return (
          <TabsContent
            key={id}
            value={id}
            forceMount
            hidden={scene !== id}
            className="mode-panel scene-panel"
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
