import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import { Laboratory } from "../components/workspace/Laboratory";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import RubberSegment from "../components/react-bits/RubberSegment";
import ElectricBorder from "../components/react-bits/ElectricBorder";
import { segmentColors } from "../components/lab/controlColors";
import {
  EvidenceFocusContext,
  type EvidenceFocus,
} from "../components/workspace/lab/evidenceFocus";
import { ExperimentPanel } from "./lab/ExperimentPanel";
import { ExperimentSide } from "./lab/ExperimentSide";
import {
  evidenceEvents,
  exerciseForExperiment,
  experimentOf,
} from "./lab/experimentRun";
import { locateEvent } from "./lab/locate";
import { RecordingView, formatRecordingDate } from "./lab/RecordingView";
import { ShortcutHelp } from "./lab/ShortcutHelp";
import { useLabShortcuts } from "./lab/useLabShortcuts";
import { useLessonRecordings } from "./lab/useLessonRecordings";
import { useRunEndToast } from "./lab/useRunEndToast";
import { useRunFollow } from "./lab/useRunFollow";
import { observeStatus } from "../content/guide";
import type { SceneProps } from "./types";

// The masked tour (React Joyride) loads only when a learner starts a guide.
const GuideTour = lazy(() => import("./lab/GuideTour"));

/** 实验：experiments frame the run; the stage, film and cards show what really happened. */
export function LabScene({ studio, active, onConfigure }: SceneProps) {
  const { t, i18n } = useTranslation("lesson", { keyPrefix: "lab" });
  const detail = studio.detail!;
  const experiments = detail.learning?.scenes.lab?.experiments ?? [];
  const [experimentId, setExperimentId] = useState(experiments[0]?.id ?? "");
  const experiment =
    experiments.find((item) => item.id === experimentId) ?? experiments[0];
  const [guideStep, setGuideStep] = useState<number | null>(null);
  const [spotlight, setSpotlight] = useState<string | null>(null);
  const [focus, setFocus] = useState<EvidenceFocus | null>(null);
  // Counts guides finished on the current run; the side card celebrates each.
  const [guidesDone, setGuidesDone] = useState(0);
  const recordings = useLessonRecordings(detail.id);
  const [source, setSource] = useState("mine");
  // Only a run of one of this experiment's arms is checked against its observe points.
  const evidence = experiment
    ? evidenceEvents(experiment, studio.runExerciseId, studio.events)
    : [];
  const finished = evidence.at(-1)?.type === "done";
  const statuses = experiment ? observeStatus(experiment, evidence) : [];
  const pathOf = (id: string) =>
    experiment?.observe.find((point) => point.id === id)?.selector?.path ??
    null;
  // The observe point whose evidence the inspector shows and frames (locate, guide, default).
  const shown = studio.active ? studio.visible.indexOf(studio.active) : -1;
  const current = statuses.find(
    (point) =>
      point.status === "found" &&
      point.index === shown &&
      focus?.index === shown &&
      focus.path === pathOf(point.id),
  )?.id;

  const resetExperiment = (id: string) => {
    setExperimentId(id);
    setGuideStep(null);
    setFocus(null);
    setGuidesDone(0);
  };

  useEffect(() => {
    resetExperiment(experiments[0]?.id ?? "");
    setSource("mine");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  // An exercise picked elsewhere (the `/` menu) brings its experiment along.
  useEffect(() => {
    if (experiment?.arms.some((arm) => arm.exercise === studio.exerciseId))
      return;
    const owner = experimentOf(experiments, studio.exerciseId);
    if (owner) resetExperiment(owner.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studio.exerciseId]);

  // Switching experiments also switches to one of its arms, so the next run belongs to it.
  const selectExperiment = (id: string) => {
    resetExperiment(id);
    const next = experiments.find((item) => item.id === id);
    const exercise =
      next && exerciseForExperiment(next, detail.exercises, studio.exerciseId);
    if (exercise) studio.selectExercise(exercise);
  };

  // A new run invalidates the guide position and the evidence of the previous one.
  useEffect(() => {
    if (studio.running) {
      setGuideStep(null);
      setFocus(null);
      setGuidesDone(0);
    }
  }, [studio.running]);

  // A finished run opens on the first observe point's evidence rather than on
  // its last event. Selecting does not rewind the replay; nothing scrolls.
  useEffect(() => {
    if (!finished || studio.running || focus || !experiment) return;
    const first = statuses.find((point) => point.status === "found");
    if (first?.status !== "found") return;
    setFocus({ index: first.index, path: pathOf(first.id), reveal: false });
    studio.selectEvent(first.index);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished, studio.running, experiment?.id]);

  // Leaving the lab scene ends a guide; it never runs over another scene.
  useEffect(() => {
    if (!active) setGuideStep(null);
  }, [active]);

  useRunEndToast(studio);

  // Leaving keeps the evidence focus: the learner stays on the last framed field.
  const exitGuide = useCallback((completed: boolean) => {
    setGuideStep(null);
    setSpotlight(null);
    if (completed) setGuidesDone((count) => count + 1);
  }, []);
  const recording = recordings.find((item) => item.name === source);
  // The view follows a run down to the observatory and back when it ends.
  const frame = useRef<HTMLDivElement>(null);
  useRunFollow(studio.running, active && !recording, frame);
  const [help, setHelp] = useState(false);
  useLabShortcuts({
    studio,
    enabled: active && !studio.running && !recording && guideStep === null,
    onHelp: () => setHelp(true),
  });

  return (
    <EvidenceFocusContext.Provider value={focus}>
      <div className="scene-lab" data-testid="scene-lab">
        {recordings.length > 0 && (
          <div className="lab-source-switch">
            <RubberSegment
              aria-label={t("source.region")}
              size="sm"
              items={[
                { value: "mine", label: t("source.mine") },
                ...recordings.map((item) => ({
                  value: item.name,
                  label: t("source.recording", {
                    model: item.metadata!.model,
                    date: formatRecordingDate(
                      item.metadata!.recorded_at,
                      i18n.language,
                    ),
                  }),
                })),
              ]}
              value={source}
              onChange={setSource}
              disabled={studio.running}
              {...segmentColors}
            />
          </div>
        )}
        {recording ? (
          <RecordingView lessonId={detail.id} recording={recording} />
        ) : (
          <>
            <div className="lab-layout">
              {experiment && (
                // Fixed beside the observatory on wide screens; scrolls inside when long.
                <aside className="lab-rail" aria-label={t("rail")}>
                  <ExperimentPanel
                    experiments={experiments}
                    selected={experiment}
                    statuses={statuses}
                    current={current ?? null}
                    onSelect={selectExperiment}
                    onLocate={(index, path) => {
                      setFocus({ index, path, reveal: true });
                      locateEvent(studio, index);
                    }}
                    studio={studio}
                  />
                  <ExperimentSide
                    experiment={experiment}
                    statuses={statuses}
                    finished={finished}
                    running={studio.running}
                    guiding={guideStep !== null}
                    guidesDone={guidesDone}
                    onStartGuide={() => setGuideStep(0)}
                  />
                </aside>
              )}
              <div
                ref={frame}
                className="lab-frame"
                data-running={studio.running || undefined}
              >
                {/* Decoration only while a real run is in progress. */}
                {studio.running && (
                  <ElectricBorder
                    className="lab-running-border"
                    color="#8f7dff"
                    chaos={0.08}
                    speed={1.2}
                    borderRadius={18}
                  />
                )}
                <LessonExtension
                  slot="lab"
                  extensionKey={detail.ui?.lab}
                  studio={studio}
                  active={active}
                  onConfigure={onConfigure}
                >
                  <Laboratory
                    studio={studio}
                    active={active}
                    onConfigure={onConfigure}
                    spotlight={guideStep !== null ? spotlight : null}
                  />
                </LessonExtension>
              </div>
            </div>
            {experiment && guideStep !== null && finished && active && (
              <Suspense fallback={null}>
                <GuideTour
                  experiment={experiment}
                  studio={studio}
                  step={guideStep}
                  onStep={setGuideStep}
                  onExit={exitGuide}
                  onFocus={setFocus}
                  onSpotlight={setSpotlight}
                />
              </Suspense>
            )}
          </>
        )}
        <ShortcutHelp open={help} onOpenChange={setHelp} />
      </div>
    </EvidenceFocusContext.Provider>
  );
}
