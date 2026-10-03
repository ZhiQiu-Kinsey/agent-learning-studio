import { Suspense, lazy, useCallback, useEffect, useState } from "react";
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
import { locateEvent } from "./lab/locate";
import { RecordingView, formatRecordingDate } from "./lab/RecordingView";
import { ShortcutHelp } from "./lab/ShortcutHelp";
import { useLabShortcuts } from "./lab/useLabShortcuts";
import { useLessonRecordings } from "./lab/useLessonRecordings";
import { useRunEndToast } from "./lab/useRunEndToast";
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
  const finished = studio.events.at(-1)?.type === "done";

  useEffect(() => {
    setExperimentId(experiments[0]?.id ?? "");
    setGuideStep(null);
    setFocus(null);
    setGuidesDone(0);
    setSource("mine");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  // A new run invalidates the guide position and the evidence of the previous one.
  useEffect(() => {
    if (studio.running) {
      setGuideStep(null);
      setFocus(null);
      setGuidesDone(0);
    }
  }, [studio.running]);

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
            {experiment && (
              <div className="lab-experiment-row">
                <ExperimentPanel
                  experiments={experiments}
                  selected={experiment}
                  onSelect={(id) => {
                    setExperimentId(id);
                    setGuideStep(null);
                    setFocus(null);
                    setGuidesDone(0);
                  }}
                  onLocate={(index, path) => {
                    setFocus({ index, path, reveal: true });
                    locateEvent(studio, index);
                  }}
                  studio={studio}
                />
                <ExperimentSide
                  experiment={experiment}
                  statuses={observeStatus(experiment, studio.events)}
                  finished={finished}
                  running={studio.running}
                  guiding={guideStep !== null}
                  guidesDone={guidesDone}
                  onStartGuide={() => setGuideStep(0)}
                />
              </div>
            )}
            <div
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
