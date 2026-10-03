import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../../motion";
import type { StudioState } from "../../hooks/useStudio";
import BorderGlow from "../react-bits/BorderGlow";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { useEvidenceFocus } from "./lab/evidenceFocus";
import { InspectorHeading } from "./lab/InspectorHeading";
import { PromptPane, SourcePane } from "./lab/LessonFiles";
import { RunObservatory } from "./lab/RunObservatory";
import { RunPanel } from "./lab/RunPanel";
import { useRunView } from "./lab/useRunView";

/**
 * The lab bench: the run panel on the left; on the right the run observatory
 * (execution record), the lesson's Python source, and its prompt and tools.
 */
export function Laboratory({
  studio: s,
  onConfigure,
  active,
  spotlight,
}: {
  studio: StudioState;
  onConfigure: () => void;
  active: boolean;
  /** Stage node role highlighted by a guided replay. */
  spotlight?: string | null;
}) {
  const reducedMotion = useReducedMotion();
  const { t } = useTranslation("lab", { keyPrefix: "bench.inspector" });
  const [tab, setTab] = useState("trace");
  const run = useRunView(s);
  // Lives here so the copy confirmation survives switching tabs.
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (s.running) setTab("trace");
  }, [s.running]);
  // Pointing at evidence (guided replay, "locate") always shows the execution record.
  const focus = useEvidenceFocus();
  useEffect(() => {
    if (focus) setTab("trace");
  }, [focus]);
  useEffect(() => {
    setCopied(false);
  }, [s.active]);
  return (
    <BorderGlow
      className="lab-border-glow"
      backgroundColor="var(--surface)"
      borderRadius={18}
      edgeSensitivity={20}
      glowColor="250 80% 72%"
      glowRadius={8}
      glowIntensity={reducedMotion ? 0 : 0.95}
      colors={["#9781ed", "#65b6d3", "#b39af0"]}
      fillOpacity={0.035}
      animated={active && !reducedMotion}
    >
      <div
        className="lab-workspace"
        data-testid="lab-workspace"
        data-running={s.running || undefined}
      >
        <RunPanel
          studio={s}
          onConfigure={onConfigure}
          onRun={() => {
            setTab("trace");
            void s.run();
          }}
        />
        <section className="lab-inspector">
          <InspectorHeading
            studio={s}
            active={active}
            completed={run.completed}
            last={run.last}
          />
          <Tabs value={tab} onValueChange={setTab} className="inspector-tabs">
            <TabsList aria-label={t("tabs")} className="inspector-tab-list">
              <TabsTrigger value="trace">{t("trace")}</TabsTrigger>
              <TabsTrigger value="source" data-testid="lab-tab-source">
                {t("source")}
              </TabsTrigger>
              <TabsTrigger value="prompt">{t("prompt")}</TabsTrigger>
            </TabsList>
            <TabsContent value="trace" className="inspector-trace">
              <RunObservatory
                studio={s}
                run={run}
                active={active}
                spotlight={spotlight}
                copied={copied}
                onCopied={() => setCopied(true)}
              />
            </TabsContent>
            <TabsContent
              value="source"
              className="lab-source source-pane"
              data-testid="lab-source-panel"
            >
              <SourcePane studio={s} />
            </TabsContent>
            <TabsContent value="prompt" className="lab-prompt">
              <PromptPane detail={s.detail} />
            </TabsContent>
          </Tabs>
        </section>
      </div>
    </BorderGlow>
  );
}
