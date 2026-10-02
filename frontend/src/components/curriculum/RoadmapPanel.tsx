import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ProgressRecord } from "../../progress";
import type { CurriculumData } from "../../types";
import { RoadmapSection } from "./RoadmapSection";
import type { GraphResult } from "./useCurriculumData";

/** Roadmap view: filters, the prerequisite graph (or why it failed) and graph notes. */
export function RoadmapPanel({
  filters,
  graphResult,
  curriculum,
  progress,
  visibleIds,
  onSelectLesson,
}: {
  filters: ReactNode;
  graphResult: GraphResult | null;
  curriculum: CurriculumData;
  progress: ProgressRecord;
  visibleIds: ReadonlySet<string>;
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const unknown =
    graphResult && "graph" in graphResult ? graphResult.graph.issues.length : 0;
  return (
    <>
      {filters}
      {graphResult && "error" in graphResult ? (
        <div className="alert" role="alert">
          {t("roadmap.failed", { reason: graphResult.error })}
        </div>
      ) : (
        graphResult && (
          <RoadmapSection
            graph={graphResult.graph}
            lessons={curriculum.lessons}
            progress={progress}
            matches={visibleIds}
            onSelectLesson={onSelectLesson}
          />
        )
      )}
      {unknown > 0 && (
        <p className="curriculum-planned-note">
          {t("roadmap.unknownPrerequisites", { n: unknown })}
        </p>
      )}
    </>
  );
}
