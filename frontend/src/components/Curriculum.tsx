import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CircleCheckBig,
  Compass,
  ExternalLink,
  Layers3,
  LayoutGrid,
  List,
  LoaderCircle,
  Route,
  Search,
  X,
  type LucideIcon,
} from "lucide-react";
import { jsonFetch } from "../api";
import { formatLessonNumber } from "../lib/lessonIds";
import { useProgress } from "../progress";
import type { CurriculumData, CurriculumLesson } from "../types";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./ui/accordion";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import SpotlightCard from "./react-bits/SpotlightCard";
import CountUp from "./react-bits/CountUp";
import SquishSwitch from "./react-bits/SquishSwitch";
import BlurText from "./react-bits/BlurText";
import StarBorder from "./react-bits/StarBorder";
import { Backdrop } from "./backdrops/Backdrop";
import { useReducedMotion } from "../motion";
import { DomainBento } from "./curriculum/DomainBento";
import { RoadmapSection } from "./curriculum/RoadmapSection";
import { ProgressMarks } from "./curriculum/ProgressMarks";
import { domainAtmosphere } from "./curriculum/atmosphere";
import {
  buildCurriculumGraph,
  CurriculumGraphError,
  lessonMarks,
  lessonMatches,
  type CurriculumGraph,
} from "./curriculum/graph";

const mapViews = ["domains", "roadmap", "list"] as const;
type MapView = (typeof mapViews)[number];
const viewStorageKey = "agent-lab-map-view";

function readView(): MapView {
  try {
    const saved = sessionStorage.getItem(viewStorageKey);
    return mapViews.includes(saved as MapView) ? (saved as MapView) : "domains";
  } catch {
    return "domains";
  }
}

/** Spring shared by the map's sliding indicators (view switch, filter chips). */
const pillSpring = {
  type: "spring",
  stiffness: 420,
  damping: 34,
  mass: 0.8,
} as const;
const easeOut = [0.16, 1, 0.3, 1] as const;

/** Hero entrance: blur-in from below, staggered by `step`. */
function HeroReveal({
  step,
  className,
  children,
}: {
  step: number;
  className?: string;
  children: ReactNode;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y: 18, filter: "blur(10px)" }}
      animate={{
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        transitionEnd: { filter: "none" },
      }}
      transition={{ duration: 0.7, delay: 0.1 + step * 0.09, ease: easeOut }}
    >
      {children}
    </motion.div>
  );
}

const viewTabs: { id: MapView; Icon: LucideIcon }[] = [
  { id: "domains", Icon: LayoutGrid },
  { id: "roadmap", Icon: Route },
  { id: "list", Icon: List },
];

/** A view arriving after a switch: rises out of a soft blur. */
function ViewPanel({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className="curriculum-view-panel"
      initial={reduced ? false : { opacity: 0, y: 14, filter: "blur(8px)" }}
      // Drop the filter afterwards: even blur(0) creates a containing block.
      animate={{
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        transitionEnd: { filter: "none" },
      }}
      transition={{ duration: 0.45, ease: easeOut }}
    >
      {children}
    </motion.div>
  );
}

/** Active filter chip background; slides between chips on a spring. */
function ChipPill() {
  const reduced = useReducedMotion();
  return (
    <motion.i
      className="curriculum-chip-pill"
      layoutId="curriculum-chip-pill"
      transition={reduced ? { duration: 0 } : pillSpring}
      aria-hidden="true"
    />
  );
}

function MapMetric({
  value,
  label,
  index,
  Icon,
  ratio,
}: {
  value: number;
  label: string;
  index: number;
  Icon: LucideIcon;
  /** Optional real share (0..1) drawn as a thin meter. */
  ratio?: number;
}) {
  const reducedMotion = useReducedMotion();
  return (
    <motion.div
      className="curriculum-metric"
      initial={reducedMotion ? false : { opacity: 0, y: 22, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.65, delay: 0.3 + index * 0.08, ease: easeOut }}
      style={
        ratio === undefined
          ? undefined
          : ({ "--ratio": ratio } as CSSProperties)
      }
    >
      <Icon className="curriculum-metric-icon" size={16} aria-hidden="true" />
      <strong>
        <span className="sr-only">{value}</span>
        <span aria-hidden="true">
          {reducedMotion ? (
            value
          ) : (
            <CountUp to={value} duration={1.1} delay={0.35 + index * 0.09} />
          )}
        </span>
      </strong>
      <span>{label}</span>
      {ratio !== undefined && (
        <span className="curriculum-metric-meter" aria-hidden="true">
          <i />
        </span>
      )}
    </motion.div>
  );
}

function sourceUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}

function TextList({ items }: { items: string[] }) {
  return (
    <ul>
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

function LessonPlan({
  lesson,
  curriculum,
  onSelectLesson,
}: {
  lesson: CurriculumLesson;
  curriculum: CurriculumData;
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const marks = lessonMarks(useProgress(), lesson);
  const prerequisiteTitles = lesson.prerequisites.map(
    (id) =>
      curriculum.lessons.find(
        (item) => item.id === id || item.aliases?.includes(id),
      )?.title || id,
  );
  return (
    <Accordion type="single" collapsible>
      <AccordionItem
        value={lesson.id}
        className="curriculum-lesson"
        data-status={lesson.status}
        data-testid="curriculum-lesson"
      >
        <AccordionTrigger
          className="curriculum-lesson-trigger"
          data-testid="curriculum-lesson-trigger"
        >
          <span className="curriculum-lesson-title">
            <strong>{lesson.title}</strong>
            <small>
              {t("lessonMeta", {
                number: formatLessonNumber(lesson.number),
                level: lesson.level,
              })}
            </small>
          </span>
          <ProgressMarks marks={marks} testId="curriculum-lesson-progress" />
          <span className={`curriculum-status ${lesson.status}`}>
            {t(`status.${lesson.status}`)}
          </span>
        </AccordionTrigger>
        <AccordionContent className="curriculum-lesson-body">
          <p className="curriculum-summary">{lesson.summary}</p>
          <div className="curriculum-prerequisites">
            <strong>{t("list.prerequisites")}</strong>
            <p>
              {prerequisiteTitles.length
                ? prerequisiteTitles.join(t("list.separator"))
                : t("list.noPrerequisites")}
            </p>
          </div>
          <div className="curriculum-detail-grid">
            <section>
              <h4>{t("list.objectives")}</h4>
              <TextList items={lesson.objectives} />
            </section>
            <section>
              <h4>{t("list.topics")}</h4>
              <div className="curriculum-topics">
                {lesson.topics.map((topic) => (
                  <span key={topic}>{topic}</span>
                ))}
              </div>
            </section>
          </div>
          <section
            className="curriculum-experiments"
            data-testid="curriculum-lesson-experiments"
          >
            <h4>{t("list.experiments")}</h4>
            {lesson.experiments.map((experiment, index) => (
              <div className="curriculum-experiment" key={index}>
                <h5>{experiment.title}</h5>
                <ol>
                  {experiment.steps.map((step, stepIndex) => (
                    <li key={stepIndex}>{step}</li>
                  ))}
                </ol>
                <p>
                  <strong>{t("list.deliverable")}</strong>
                  {experiment.deliverable}
                </p>
              </div>
            ))}
          </section>
          <section>
            <h4>{t("list.acceptance")}</h4>
            <TextList items={lesson.acceptance} />
          </section>
          <section className="curriculum-references">
            <h4>{t("list.references")}</h4>
            <ul>
              {lesson.references.map((reference, index) => {
                const source = curriculum.sources.find(
                  (item) => item.id === reference.source,
                );
                const url = source ? sourceUrl(source.url) : undefined;
                return (
                  <li key={index}>
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer">
                        {source?.title}
                        <ExternalLink size={11} />
                      </a>
                    ) : (
                      <span>{source?.title || reference.source}</span>
                    )}
                    <span> · {reference.locator}</span>
                  </li>
                );
              })}
            </ul>
          </section>
          {lesson.status === "available" ? (
            <Button
              className="primary-button"
              data-testid="curriculum-lesson-start"
              onClick={() => onSelectLesson(lesson.id)}
            >
              {t("list.start", { number: lesson.number })}
              <ArrowRight size={14} />
            </Button>
          ) : (
            <p className="curriculum-planned-note">{t("list.plannedNote")}</p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

function Filters({
  curriculum,
  query,
  setQuery,
  onlyAvailable,
  setOnlyAvailable,
  activeCategory,
  setActiveCategory,
  visibleCount,
  onReset,
}: {
  curriculum: CurriculumData;
  query: string;
  setQuery: (value: string) => void;
  onlyAvailable: boolean;
  setOnlyAvailable: (value: boolean) => void;
  activeCategory: string | null;
  setActiveCategory: (value: string | null) => void;
  visibleCount: number;
  onReset: () => void;
}) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  return (
    <div
      className="panel curriculum-controls"
      data-testid="curriculum-controls"
    >
      <div className="curriculum-search">
        <label className="field-label" htmlFor="curriculum-search">
          {t("filters.search")}
        </label>
        <div>
          <Search size={16} aria-hidden="true" />
          <Input
            id="curriculum-search"
            data-testid="curriculum-search-input"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("filters.searchPlaceholder")}
          />
        </div>
      </div>
      <SquishSwitch
        className="curriculum-filter"
        label={t("filters.onlyAvailable")}
        ariaLabel={t("filters.onlyAvailable")}
        checked={onlyAvailable}
        onChange={setOnlyAvailable}
        width={38}
        height={22}
        trackColor="var(--border)"
        trackOnColor="var(--text-accent)"
        thumbColor="var(--surface)"
        thumbOnColor="var(--surface)"
      />
      <span className="curriculum-result-count" role="status">
        <motion.span
          key={visibleCount}
          initial={reduced ? false : { opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: easeOut }}
        >
          {t("filters.count", {
            visible: visibleCount,
            total: curriculum.lessons.length,
          })}
        </motion.span>
      </span>
      <div
        className="curriculum-category-filter"
        role="group"
        aria-label={t("filters.category")}
        data-testid="curriculum-category-filter"
      >
        <button
          type="button"
          aria-pressed={!activeCategory}
          onClick={() => setActiveCategory(null)}
        >
          {!activeCategory && <ChipPill />}
          <span>{t("filters.allCategories")}</span>
        </button>
        {curriculum.categories.map((category) => (
          <button
            key={category.id}
            type="button"
            data-category={category.id}
            aria-pressed={activeCategory === category.id}
            style={
              {
                "--chip-rgb": domainAtmosphere(category.id).accent,
              } as CSSProperties
            }
            onClick={() =>
              setActiveCategory(
                activeCategory === category.id ? null : category.id,
              )
            }
          >
            {activeCategory === category.id && <ChipPill />}
            <span>{category.title}</span>
          </button>
        ))}
        <AnimatePresence>
          {(activeCategory || query || onlyAvailable) && (
            <motion.button
              type="button"
              className="curriculum-reset"
              onClick={onReset}
              initial={reduced ? false : { opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={reduced ? undefined : { opacity: 0, scale: 0.8 }}
              transition={pillSpring}
            >
              <X size={13} aria-hidden="true" />
              {t("filters.reset")}
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function LessonList({
  curriculum,
  visibleIds,
  onSelectLesson,
  onReset,
}: {
  curriculum: CurriculumData;
  visibleIds: ReadonlySet<string>;
  onSelectLesson: (id: string) => void;
  onReset: () => void;
}) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  return (
    <>
      {!visibleIds.size && (
        <motion.div
          className="panel curriculum-no-results"
          initial={
            reduced ? false : { opacity: 0, scale: 0.97, filter: "blur(6px)" }
          }
          animate={{
            opacity: 1,
            scale: 1,
            filter: "blur(0px)",
            transitionEnd: { filter: "none" },
          }}
          transition={{ duration: 0.4, ease: easeOut }}
        >
          <Search size={26} aria-hidden="true" />
          <h3>{t("filters.emptyTitle")}</h3>
          <p>{t("filters.emptyHelp")}</p>
          <Button variant="outline" onClick={onReset}>
            {t("filters.showAll")}
          </Button>
        </motion.div>
      )}
      {curriculum.categories.map((category, index) => {
        const modules = category.modules.filter((module) =>
          module.lesson_ids.some((id) => visibleIds.has(id)),
        );
        if (!modules.length) return null;
        const { accent } = domainAtmosphere(category.id);
        return (
          <motion.div
            key={category.id}
            className="curriculum-category-reveal"
            style={{ "--domain-rgb": accent } as CSSProperties}
            initial={reduced ? false : { opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.04 }}
            transition={{ duration: 0.6, ease: easeOut }}
          >
            <SpotlightCard
              className="panel curriculum-category"
              spotlightColor={
                `rgba(${accent}, 0.1)` as `rgba(${number}, ${number}, ${number}, ${number})`
              }
            >
              <div
                className="curriculum-category-heading"
                data-testid="curriculum-category-heading"
              >
                <span className="curriculum-category-number" aria-hidden="true">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <h2>{category.title}</h2>
                  <p>{category.description}</p>
                </div>
                <span className="curriculum-category-label">
                  {t("list.modules", { n: modules.length })}
                  <ArrowDown size={13} />
                </span>
              </div>
              {modules.map((module) => {
                const ids = module.lesson_ids.filter((id) =>
                  visibleIds.has(id),
                );
                return (
                  <div
                    className="curriculum-module"
                    key={module.id}
                    data-testid="curriculum-module"
                  >
                    <div className="curriculum-module-intro">
                      <span className="curriculum-module-kicker">
                        {t("list.moduleKicker", { id: module.id })}
                      </span>
                      <h3>{module.title}</h3>
                      <p>{module.description}</p>
                      <span className="curriculum-module-count">
                        {t("list.lessons", { n: ids.length })}
                        <ArrowRight size={12} />
                      </span>
                    </div>
                    <div className="curriculum-module-lessons">
                      <AnimatePresence initial={!reduced}>
                        {ids.map((id, row) => (
                          <motion.div
                            key={id}
                            className="curriculum-lesson-row"
                            initial={
                              reduced
                                ? false
                                : { opacity: 0, x: -14, filter: "blur(6px)" }
                            }
                            whileInView={{
                              opacity: 1,
                              x: 0,
                              filter: "blur(0px)",
                              transitionEnd: { filter: "none" },
                            }}
                            viewport={{ once: true, amount: 0.2 }}
                            exit={
                              reduced
                                ? undefined
                                : {
                                    opacity: 0,
                                    x: 10,
                                    transition: { duration: 0.14 },
                                  }
                            }
                            transition={{
                              duration: 0.45,
                              delay: Math.min(row, 8) * 0.045,
                              ease: easeOut,
                            }}
                          >
                            <LessonPlan
                              lesson={curriculum.lessons.find(
                                (item) => item.id === id,
                              )!}
                              curriculum={curriculum}
                              onSelectLesson={onSelectLesson}
                            />
                          </motion.div>
                        ))}
                      </AnimatePresence>
                    </div>
                  </div>
                );
              })}
            </SpotlightCard>
          </motion.div>
        );
      })}
      {curriculum.electives.length > 0 && (
        <section className="panel curriculum-supplement">
          <h2>{t("supplements.electives")}</h2>
          <p>{t("supplements.electivesHelp")}</p>
          <Accordion type="multiple">
            {curriculum.electives.map((elective) => (
              <AccordionItem
                className="curriculum-elective"
                key={elective.id}
                value={elective.id}
              >
                <AccordionTrigger className="curriculum-elective-trigger">
                  {elective.title}
                </AccordionTrigger>
                <AccordionContent>
                  <p>{elective.description}</p>
                  <h4>{t("supplements.prerequisites")}</h4>
                  <p>
                    {elective.prerequisites
                      .map(
                        (id) =>
                          curriculum.lessons.find((lesson) => lesson.id === id)
                            ?.title || id,
                      )
                      .join(t("list.separator")) || t("supplements.none")}
                  </p>
                  <h4>{t("supplements.topics")}</h4>
                  <TextList items={elective.topics} />
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      )}
      <section className="panel curriculum-supplement curriculum-principles-panel">
        <h2>{t("supplements.principles")}</h2>
        <TextList items={curriculum.principles} />
      </section>
      <section className="panel curriculum-supplement curriculum-sources-panel">
        <h2>{t("supplements.sources")}</h2>
        <div className="curriculum-source-grid">
          {curriculum.sources.map((source) => {
            const url = sourceUrl(source.url);
            return (
              <div className="curriculum-source" key={source.id}>
                <h3>
                  {url ? (
                    <a href={url} target="_blank" rel="noopener noreferrer">
                      {source.title}
                      <ExternalLink size={13} />
                    </a>
                  ) : (
                    source.title
                  )}
                </h3>
                <p>{source.role}</p>
                <p>{source.adaptation}</p>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

export function Curriculum({
  onSelectLesson,
}: {
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const progress = useProgress();
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [view, setViewState] = useState<MapView>(readView);
  const [query, setQuery] = useState("");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const reduced = useReducedMotion();

  const setView = (value: string) => {
    if (!mapViews.includes(value as MapView)) return;
    setViewState(value as MapView);
    try {
      sessionStorage.setItem(viewStorageKey, value);
    } catch {
      /* The choice still applies to this visit. */
    }
  };

  useEffect(() => {
    let ignore = false;
    setError("");
    jsonFetch<CurriculumData>("/api/curriculum")
      .then((data) => {
        if (!ignore) setCurriculum(data);
      })
      .catch((reason) => {
        if (!ignore)
          setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      ignore = true;
    };
  }, [attempt]);

  const graphResult = useMemo<
    { graph: CurriculumGraph } | { error: string } | null
  >(() => {
    if (!curriculum) return null;
    try {
      return { graph: buildCurriculumGraph(curriculum.lessons) };
    } catch (reason) {
      if (reason instanceof CurriculumGraphError)
        return { error: reason.message };
      throw reason;
    }
  }, [curriculum]);

  const filter = { query, onlyAvailable, categoryId: activeCategory };
  const visibleIds = useMemo(
    () =>
      new Set(
        curriculum?.lessons
          .filter((lesson) => lessonMatches(lesson, curriculum, filter))
          .map((lesson) => lesson.id) ?? [],
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [curriculum, query, onlyAvailable, activeCategory],
  );

  if (!curriculum) {
    return (
      <section className="panel curriculum-loading">
        <h1>{t("title")}</h1>
        {error ? (
          <div className="alert" role="alert">
            <span>{t("loadFailed", { reason: error })}</span>
            <Button
              className="text-button"
              onClick={() => setAttempt((previous) => previous + 1)}
            >
              {t("retry")}
            </Button>
          </div>
        ) : (
          <p role="status">
            <LoaderCircle size={18} className="spin" />
            {t("loading")}
          </p>
        )}
      </section>
    );
  }

  const availableCount = curriculum.lessons.filter(
    (lesson) => lesson.status === "available",
  ).length;
  const moduleCount = curriculum.categories.reduce(
    (sum, category) => sum + category.modules.length,
    0,
  );
  const lastLesson = curriculum.lessons.find(
    (lesson) =>
      lesson.status === "available" &&
      progress.lastLessonId &&
      (lesson.id === progress.lastLessonId ||
        lesson.aliases?.includes(progress.lastLessonId)),
  );
  const firstAvailable = curriculum.lessons.find(
    (lesson) => lesson.status === "available",
  );
  const resetFilters = () => {
    setActiveCategory(null);
    setQuery("");
    setOnlyAvailable(false);
  };
  const filters = (
    <Filters
      curriculum={curriculum}
      query={query}
      setQuery={setQuery}
      onlyAvailable={onlyAvailable}
      setOnlyAvailable={setOnlyAvailable}
      activeCategory={activeCategory}
      setActiveCategory={setActiveCategory}
      visibleCount={visibleIds.size}
      onReset={resetFilters}
    />
  );
  const unknown =
    graphResult && "graph" in graphResult ? graphResult.graph.issues.length : 0;

  return (
    <div className="curriculum-view" data-testid="curriculum-map">
      <header
        className="curriculum-map-header curriculum-hero"
        aria-labelledby="curriculum-title"
      >
        <Backdrop name="topography" className="curriculum-hero-backdrop" />
        <div className="curriculum-hero-scrim" aria-hidden="true" />
        <div className="curriculum-map-copy">
          <HeroReveal step={0}>
            <span className="curriculum-eyebrow">
              <Compass size={15} aria-hidden="true" />
              {t("eyebrow", { version: curriculum.version })}
            </span>
          </HeroReveal>
          <h1 id="curriculum-title" data-testid="curriculum-title">
            <BlurText text={t("title")} delay={90} />
          </h1>
          <HeroReveal step={2}>
            <p className="curriculum-hero-description">
              {t("description", { title: curriculum.title })}
            </p>
          </HeroReveal>
          <HeroReveal step={3} className="curriculum-hero-actions">
            {(lastLesson ?? firstAvailable) && (
              <StarBorder
                className="curriculum-start-star"
                color="#49dec6"
                speed="6s"
              >
                <Button
                  className="curriculum-start-button"
                  onClick={() =>
                    onSelectLesson((lastLesson ?? firstAvailable)!.id)
                  }
                >
                  {lastLesson
                    ? t("resume", { number: lastLesson.number })
                    : t("start", { number: firstAvailable!.number })}
                  <ArrowUpRight size={16} />
                </Button>
              </StarBorder>
            )}
            <Button
              variant="ghost"
              className="curriculum-hero-route"
              onClick={() => setView("roadmap")}
            >
              <Route size={15} aria-hidden="true" />
              {t("hero.route")}
            </Button>
          </HeroReveal>
        </div>
        <div className="curriculum-stats" aria-label={t("stats.label")}>
          <MapMetric
            value={curriculum.categories.length}
            label={t("stats.domains")}
            index={0}
            Icon={Compass}
          />
          <MapMetric
            value={moduleCount}
            label={t("stats.modules")}
            index={1}
            Icon={Layers3}
          />
          <MapMetric
            value={curriculum.lessons.length}
            label={t("stats.lessons")}
            index={2}
            Icon={BookOpen}
          />
          <MapMetric
            value={availableCount}
            label={t("stats.available")}
            index={3}
            Icon={CircleCheckBig}
            ratio={
              curriculum.lessons.length
                ? availableCount / curriculum.lessons.length
                : 0
            }
          />
        </div>
      </header>
      <Tabs value={view} onValueChange={setView} className="curriculum-tabs">
        <TabsList
          variant="line"
          className="curriculum-view-switch"
          aria-label={t("views.label")}
          data-testid="curriculum-view-switch"
        >
          {viewTabs.map(({ id, Icon }) => (
            <TabsTrigger
              key={id}
              value={id}
              data-testid={`curriculum-view-${id}`}
            >
              {view === id && (
                <motion.i
                  className="curriculum-view-pill"
                  layoutId="curriculum-view-pill"
                  transition={reduced ? { duration: 0 } : pillSpring}
                  aria-hidden="true"
                />
              )}
              <Icon aria-hidden="true" />
              <span>{t(`views.${id}`)}</span>
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="domains">
          <ViewPanel>
            <DomainBento
              curriculum={curriculum}
              progress={progress}
              onOpenDomain={(id) => {
                setActiveCategory(id);
                setView("list");
              }}
            />
          </ViewPanel>
        </TabsContent>
        <TabsContent value="roadmap">
          <ViewPanel>
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
          </ViewPanel>
        </TabsContent>
        <TabsContent value="list">
          <ViewPanel>
            {filters}
            <LessonList
              curriculum={curriculum}
              visibleIds={visibleIds}
              onSelectLesson={onSelectLesson}
              onReset={resetFilters}
            />
          </ViewPanel>
        </TabsContent>
      </Tabs>
    </div>
  );
}
