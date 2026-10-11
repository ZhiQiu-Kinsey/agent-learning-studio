import { lazy, Suspense, useEffect, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../motion";
import { formatLessonNumber } from "../lib/lessonIds";
import { useCurriculum } from "../hooks/useCurriculum";
import { track } from "../progress";
import { Tabs, TabsContent } from "../components/ui/tabs";
import { LessonVocabulary } from "../content/glossary/Glossary";
import type { StudioState } from "../hooks/useStudio";
import { TranslationNotice } from "../components/TranslationNotice";
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
/** Other parts of the app (command palette, CTAs) can ask for a scene. */
export const SCENE_EVENT = "agent-lab:scene";
export function requestScene(scene: SceneId) {
  window.dispatchEvent(
    new CustomEvent<SceneId>(SCENE_EVENT, { detail: scene }),
  );
}

interface LessonScenesProps {
  studio: StudioState;
  /** False while the curriculum map or onboarding covers the lesson page. */
  visible: boolean;
  onConfigure: () => void;
}

const noNames: string[] = [];
const noNotes: { name: string; note: string }[] = [];

/** Every scene of a lesson reads its words through the lesson's vocabulary. */
export function LessonScenes(props: LessonScenesProps) {
  const detail = props.studio.detail;
  return (
    <LessonVocabulary
      lessonId={detail?.id ?? ""}
      codeNames={detail?.code_names ?? noNames}
      notes={detail?.learning?.code_notes ?? noNotes}
    >
      <LessonScenesBody {...props} />
    </LessonVocabulary>
  );
}

function LessonScenesBody({ studio, visible, onConfigure }: LessonScenesProps) {
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
  const categoryEntry = curriculum?.categories.find(
    (item) => item.id === category,
  );
  const categoryTitle = categoryEntry?.title;
  const moduleTitle = lessonId
    ? categoryEntry?.modules.find((module) =>
        module.lesson_ids.includes(lessonId),
      )?.title
    : undefined;

  const goTo = (next: SceneId, { scroll = true } = {}) => {
    setScene(next);
    setOpened((previous) =>
      previous.has(next) ? previous : new Set(previous).add(next),
    );
    if (scroll)
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

  // A run started from another scene (command palette) brings the learner to
  // the lab, where the view follows the run (useRunFollow); goTo does not
  // scroll. Already in the lab, the scene stays as it is.
  useEffect(() => {
    if (studio.running && scene !== "lab") goTo("lab", { scroll: false });
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
        subtitle={detail.subtitle}
        description={detail.description}
        objectives={detail.objectives}
        capabilities={capabilities}
        category={category}
        categoryTitle={categoryTitle}
        moduleTitle={moduleTitle}
        scene={scene}
        running={studio.running}
        visible={visible}
        onSource={() => goTo("code")}
      />
      <TranslationNotice info={detail.learning_i18n} />
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
