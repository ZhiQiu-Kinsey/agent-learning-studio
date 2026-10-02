import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Laboratory } from "../components/workspace/Laboratory";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import RubberSegment from "../components/react-bits/RubberSegment";
import ElectricBorder from "../components/react-bits/ElectricBorder";
import { segmentColors } from "../components/lab/controlColors";
import { ExperimentPanel } from "./lab/ExperimentPanel";
import { ExperimentSide } from "./lab/ExperimentSide";
import { GuideBar } from "./lab/GuideBar";
import { RecordingView, formatRecordingDate } from "./lab/RecordingView";
import { ShortcutHelp } from "./lab/ShortcutHelp";
import { useLabShortcuts } from "./lab/useLabShortcuts";
import { useLessonRecordings } from "./lab/useLessonRecordings";
import { useRunEndToast } from "./lab/useRunEndToast";
import { observeStatus } from "../content/guide";
import type { SceneProps } from "./types";

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
  const recordings = useLessonRecordings(detail.id);
  const [source, setSource] = useState("mine");
  const finished = studio.events.at(-1)?.type === "done";

  useEffect(() => {
    setExperimentId(experiments[0]?.id ?? "");
    setGuideStep(null);
    setSource("mine");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  // A new run invalidates the guide position on the previous one.
  useEffect(() => {
    if (studio.running) setGuideStep(null);
  }, [studio.running]);

  useRunEndToast(studio);

  const exitGuide = useCallback(() => setGuideStep(null), []);
  const recording = recordings.find((item) => item.name === source);
  const [help, setHelp] = useState(false);
  useLabShortcuts({
    studio,
    enabled: active && !studio.running && !recording,
    guideActive: guideStep !== null && finished,
    onHelp: () => setHelp(true),
  });

  return (
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
                }}
                studio={studio}
              />
              <ExperimentSide
                experiment={experiment}
                statuses={observeStatus(experiment, studio.events)}
                finished={finished}
                running={studio.running}
                guiding={guideStep !== null}
                onStartGuide={() => setGuideStep(0)}
              />
            </div>
          )}
          <div className="lab-frame" data-running={studio.running || undefined}>
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
                spotlight={spotlight}
              />
            </LessonExtension>
          </div>
          {experiment && guideStep !== null && finished && (
            <GuideBar
              experiment={experiment}
              studio={studio}
              step={guideStep}
              onStep={setGuideStep}
              onExit={exitGuide}
              onSpotlight={setSpotlight}
            />
          )}
        </>
      )}
      <ShortcutHelp open={help} onOpenChange={setHelp} />
    </div>
  );
}
