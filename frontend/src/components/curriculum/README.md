# Course map

`../Curriculum.tsx` renders the course map with three views: domains, roadmap and list. Everything shown comes from `/api/curriculum` and, for progress, from the local records in `src/progress/` (opened, completed a run, self-checked). Nothing here judges mastery.

- `graph.ts`: pure data. Prerequisite graph (alias resolution, duplicate collapse, unknown/self prerequisites dropped and reported or thrown in strict mode, cycles always throw, implied edges hidden), filters, progress marks, spatial keyboard navigation and narrow-screen stages. Unit tests in `__tests__/`.
- `layout.ts`: ELK layered layout (elkjs, EPL-2.0), loaded only with the roadmap chunk.
- `RoadmapView.tsx`: lazy-loaded @xyflow/react canvas. Nodes are buttons with a roving tabindex; arrow keys move between lessons, Enter opens an available lesson, planned lessons only show their plan. Panning/zooming uses the Controls; reduced motion makes viewport moves instant. The file only assembles the parts in `roadmap/` (all inside the lazy chunk):
  - `useRoadmapLayout.ts`: ELK positions, layout error and node centres;
  - `useRoadmapElements.ts`: React Flow nodes (marks, filter dimming, per-column entrance delay) and edges (available / planned / linked classes);
  - `useRoadmapFocus.ts`: the focused lesson, roving focus, arrow/Home/End navigation, keeping the focus in view;
  - `useRoadmapEntrance.ts`: edge current and one-time node entrance, only while on screen;
  - `LessonNode.tsx`, `RoadmapDetail.tsx`, and `nodeControls.ts` (node data types and the controls context).
- `RoadmapSection.tsx`: switches to a vertical stage list at 720px and below, so the page never scrolls sideways.
- `DomainBento.tsx`: domain tiles on React Bits [MagicBento](../react-bits/MagicBento.tsx) (MIT + Commons Clause, see `../react-bits/LICENSE.md`), with CountUp for lesson counts. Particles and the spotlight only run at the full motion level while the grid is on screen; only the hovered tile animates, so a single looping effect is ever visible.

`../Curriculum.tsx` only assembles the pieces below:

- Data hooks: `useCurriculumData.ts` (fetch with retry, derived graph), `useMapView.ts` (view kept in sessionStorage), `useLessonFilter.ts` (search / only-available / domain, shared by roadmap and list).
- `CurriculumHero.tsx` + `MapMetric.tsx`: masthead, resume/start action and real catalogue counts. `CurriculumLoading.tsx`: loading and retry.
- `ViewSwitch.tsx` (GooeyNav tab list), `ViewPanel.tsx` (view entrance), `RoadmapPanel.tsx` (roadmap view container).
- List view: `CurriculumFilters.tsx`, `LessonList.tsx`, `CategoryBlock.tsx` (domain block, modules, lesson rows), `LessonPlan.tsx` (lesson detail), `Supplements.tsx` (electives, principles, sources).
- `transitions.ts`: shared spring and easing (easing comes from `src/motion/tokens.ts`).

The list view keeps the existing SpotlightCard categories and SquishSwitch filter. RotatingText and GlareHover were removed with the old hero: they added continuous motion next to MagicBento.
