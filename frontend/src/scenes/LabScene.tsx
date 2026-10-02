import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Play } from "lucide-react";
import { jsonFetch } from "../api";
import { Laboratory } from "../components/workspace/Laboratory";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import { Button } from "../components/ui/button";
import RubberSegment from "../components/react-bits/RubberSegment";
import { ExperimentPanel } from "./lab/ExperimentPanel";
import { GuideBar } from "./lab/GuideBar";
import { RecordingView, type RecordingMeta } from "./lab/RecordingView";
import { ShortcutHelp } from "./lab/ShortcutHelp";
import { useLabShortcuts } from "./lab/useLabShortcuts";
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
  const [recordings, setRecordings] = useState<RecordingMeta[]>([]);
  const [source, setSource] = useState("mine");
  const finished = studio.events.at(-1)?.type === "done";

  useEffect(() => {
    setExperimentId(experiments[0]?.id ?? "");
    setGuideStep(null);
    setSource("mine");
    const abort = new AbortController();
    jsonFetch<{ recordings: RecordingMeta[] }>(
      `/api/lessons/${encodeURIComponent(detail.id)}/recordings`,
      { signal: abort.signal },
    )
      .then((value) => {
        if (!abort.signal.aborted)
          setRecordings(
            value.recordings.filter((item) => item.valid && item.metadata),
          );
      })
      .catch(() => {
        if (!abort.signal.aborted) setRecordings([]);
      });
    return () => abort.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  // A new run invalidates the guide position on the previous one.
  useEffect(() => {
    if (studio.running) setGuideStep(null);
  }, [studio.running]);

  const exitGuide = useCallback(() => setGuideStep(null), []);
  const recording = recordings.find((item) => item.name === source);
  const [help, setHelp] = useState(false);
  useLabShortcuts({
    studio,
    enabled: active && !studio.running && !recording,
    guideActive: guideStep !== null && finished,
    onHelp: () => setHelp(true),
  });
  const dateOf = (item: RecordingMeta) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(
      new Date(item.metadata!.recorded_at),
    );

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
                  date: dateOf(item),
                }),
              })),
            ]}
            value={source}
            onChange={setSource}
            disabled={studio.running}
            trackColor="var(--surface-muted)"
            thumbColor="var(--surface)"
            textColor="var(--text-muted)"
            activeTextColor="var(--text)"
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
              <section className="experiment-side">
                {experiment.guide.length > 0 && (
                  <div className="experiment-guide-start">
                    <Button
                      size="sm"
                      disabled={
                        !finished || studio.running || guideStep !== null
                      }
                      data-testid="guide-start"
                      onClick={() => setGuideStep(0)}
                    >
                      <Play size={14} aria-hidden="true" />
                      {t("guide.start")}
                    </Button>
                    {!finished && <small>{t("guide.needRun")}</small>}
                  </div>
                )}
                {experiment.conclusion && (
                  <div
                    className="experiment-conclusion"
                    data-testid="experiment-conclusion"
                  >
                    <h4>{t("conclusion.title")}</h4>
                    {finished ? (
                      <>
                        {experiment.conclusion.proves.length > 0 && (
                          <>
                            <strong>{t("conclusion.proves")}</strong>
                            <ul>
                              {experiment.conclusion.proves.map(
                                (item, index) => (
                                  <li key={index}>{item}</li>
                                ),
                              )}
                            </ul>
                          </>
                        )}
                        {experiment.conclusion.does_not_prove.length > 0 && (
                          <>
                            <strong>{t("conclusion.doesNotProve")}</strong>
                            <ul>
                              {experiment.conclusion.does_not_prove.map(
                                (item, index) => (
                                  <li key={index}>{item}</li>
                                ),
                              )}
                            </ul>
                          </>
                        )}
                      </>
                    ) : (
                      <p>{t("conclusion.needRun")}</p>
                    )}
                  </div>
                )}
              </section>
            </div>
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
