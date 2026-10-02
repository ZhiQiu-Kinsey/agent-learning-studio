import { useProgress } from "../progress";
import { Tabs, TabsContent } from "./ui/tabs";
import { CurriculumFilters } from "./curriculum/CurriculumFilters";
import { CurriculumHero } from "./curriculum/CurriculumHero";
import { CurriculumLoading } from "./curriculum/CurriculumLoading";
import { DomainBento } from "./curriculum/DomainBento";
import { LessonList } from "./curriculum/LessonList";
import { RoadmapPanel } from "./curriculum/RoadmapPanel";
import { useCurriculumData } from "./curriculum/useCurriculumData";
import { useLessonFilter } from "./curriculum/useLessonFilter";
import { useMapView } from "./curriculum/useMapView";
import { ViewPanel } from "./curriculum/ViewPanel";
import { ViewSwitch } from "./curriculum/ViewSwitch";

/** Course map: hero, then the domains / roadmap / list views (see curriculum/README.md). */
export function Curriculum({
  onSelectLesson,
}: {
  onSelectLesson: (id: string) => void;
}) {
  const progress = useProgress();
  const { curriculum, error, retry, graphResult } = useCurriculumData();
  const [view, setView] = useMapView();
  const filter = useLessonFilter(curriculum);

  if (!curriculum) return <CurriculumLoading error={error} onRetry={retry} />;

  const filters = <CurriculumFilters curriculum={curriculum} filter={filter} />;

  return (
    <div className="curriculum-view" data-testid="curriculum-map">
      <CurriculumHero
        curriculum={curriculum}
        progress={progress}
        onSelectLesson={onSelectLesson}
        onShowRoute={() => setView("roadmap")}
      />
      <Tabs value={view} onValueChange={setView} className="curriculum-tabs">
        <ViewSwitch view={view} />
        <TabsContent value="domains">
          <ViewPanel>
            <DomainBento
              curriculum={curriculum}
              progress={progress}
              onOpenDomain={(id) => {
                filter.setActiveCategory(id);
                setView("list");
              }}
            />
          </ViewPanel>
        </TabsContent>
        <TabsContent value="roadmap">
          <ViewPanel>
            <RoadmapPanel
              filters={filters}
              graphResult={graphResult}
              curriculum={curriculum}
              progress={progress}
              visibleIds={filter.visibleIds}
              onSelectLesson={onSelectLesson}
            />
          </ViewPanel>
        </TabsContent>
        <TabsContent value="list">
          <ViewPanel>
            {filters}
            <LessonList
              curriculum={curriculum}
              visibleIds={filter.visibleIds}
              onSelectLesson={onSelectLesson}
              onReset={filter.reset}
            />
          </ViewPanel>
        </TabsContent>
      </Tabs>
    </div>
  );
}
