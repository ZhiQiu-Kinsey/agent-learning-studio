import { useEffect, useState, type CSSProperties } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Braces,
  Check,
  Compass,
  Database,
  ExternalLink,
  Layers3,
  LoaderCircle,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  Waypoints,
  Workflow,
  X,
} from "lucide-react";
import { jsonFetch } from "../api";
import { formatLessonNumber } from "../lib/lessonIds";
import type { CurriculumData, CurriculumLesson } from "../types";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./ui/accordion";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import SpotlightCard from "./react-bits/SpotlightCard";
import AnimatedContent from "./react-bits/AnimatedContent";
import CountUp from "./react-bits/CountUp";
import ShinyText from "./react-bits/ShinyText";
import SquishSwitch from "./react-bits/SquishSwitch";
import { useReducedMotion } from "../motion";
import RotatingText from "./curriculum/RotatingText";
import GlareHover from "./curriculum/GlareHover";

const domainIcons = [
  Terminal,
  Braces,
  Layers3,
  Database,
  Workflow,
  ShieldCheck,
  Network,
  Sparkles,
];
const domainColors = [
  "#8b78e6",
  "#519fd4",
  "#a578ce",
  "#3b9e94",
  "#c28750",
  "#739b52",
  "#a56cae",
  "#ce768e",
];
const heroWords = ["可靠的 Agent", "可控的工作流", "真实的应用"];

function MapMetric({
  value,
  label,
  index,
}: {
  value: number;
  label: string;
  index: number;
}) {
  const reducedMotion = useReducedMotion();
  return (
    <div className="curriculum-metric">
      <strong>
        <span className="sr-only">{value}</span>
        <span aria-hidden="true">
          {reducedMotion ? (
            value
          ) : (
            <CountUp to={value} duration={1.1} delay={index * 0.09} />
          )}
        </span>
      </strong>
      <span>{label}</span>
    </div>
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
  const prerequisiteTitles = lesson.prerequisites.map(
    (id) => curriculum.lessons.find((item) => item.id === id)?.title || id,
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
              第 {formatLessonNumber(lesson.number)} 课 · {lesson.level}
            </small>
          </span>
          <span className={`curriculum-status ${lesson.status}`}>
            {lesson.status === "available" ? "可运行" : "计划中"}
          </span>
        </AccordionTrigger>
        <AccordionContent className="curriculum-lesson-body">
          <p className="curriculum-summary">{lesson.summary}</p>
          <div className="curriculum-prerequisites">
            <strong>先修课程</strong>
            <p>
              {prerequisiteTitles.length
                ? prerequisiteTitles.join("；")
                : "无，可以从这一课开始。"}
            </p>
          </div>
          <div className="curriculum-detail-grid">
            <section>
              <h4>学习目标</h4>
              <TextList items={lesson.objectives} />
            </section>
            <section>
              <h4>知识点</h4>
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
            <h4>实验计划</h4>
            {lesson.experiments.map((experiment, index) => (
              <div className="curriculum-experiment" key={index}>
                <h5>{experiment.title}</h5>
                <ol>
                  {experiment.steps.map((step, stepIndex) => (
                    <li key={stepIndex}>{step}</li>
                  ))}
                </ol>
                <p>
                  <strong>交付物：</strong>
                  {experiment.deliverable}
                </p>
              </div>
            ))}
          </section>
          <section>
            <h4>验收要求</h4>
            <TextList items={lesson.acceptance} />
          </section>
          <section className="curriculum-references">
            <h4>参考资料</h4>
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
              开始第 {lesson.number} 课<ArrowRight size={14} />
            </Button>
          ) : (
            <p className="curriculum-planned-note">
              课程计划已列出，讲解、代码与练习将逐课补充。
            </p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export function Curriculum({
  onSelectLesson,
}: {
  onSelectLesson: (id: string) => void;
}) {
  const reduceMotion = useReducedMotion();
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

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

  if (!curriculum) {
    return (
      <section className="panel curriculum-loading">
        <h1>完整课程表</h1>
        {error ? (
          <div className="alert" role="alert">
            <span>课程表加载失败：{error}</span>
            <Button
              className="text-button"
              onClick={() => setAttempt((previous) => previous + 1)}
            >
              重新加载
            </Button>
          </div>
        ) : (
          <p role="status">
            <LoaderCircle size={18} className="spin" />
            正在读取完整课程表…
          </p>
        )}
      </section>
    );
  }

  const needle = query.trim().toLocaleLowerCase();
  const visible = curriculum.lessons.filter((lesson) => {
    if (activeCategory && lesson.category_id !== activeCategory) return false;
    if (onlyAvailable && lesson.status !== "available") return false;
    const category = curriculum.categories.find(
      (item) => item.id === lesson.category_id,
    );
    const module = category?.modules.find(
      (item) => item.id === lesson.module_id,
    );
    return (
      !needle ||
      [
        lesson.title,
        lesson.summary,
        lesson.level,
        category?.title,
        module?.title,
        ...lesson.topics,
        ...lesson.objectives,
        ...lesson.experiments.map((experiment) => experiment.title),
      ]
        .join(" ")
        .toLocaleLowerCase()
        .includes(needle)
    );
  });
  const visibleIds = new Set(visible.map((lesson) => lesson.id));
  const availableCount = curriculum.lessons.filter(
    (lesson) => lesson.status === "available",
  ).length;
  const moduleCount = curriculum.categories.reduce(
    (sum, category) => sum + category.modules.length,
    0,
  );
  const activeDomain = curriculum.categories.find(
    (category) => category.id === activeCategory,
  );
  const firstAvailable = curriculum.lessons.find(
    (lesson) => lesson.status === "available",
  );
  const resetFilters = () => {
    setActiveCategory(null);
    setQuery("");
    setOnlyAvailable(false);
  };

  return (
    <div className="curriculum-view">
      <AnimatedContent distance={24} duration={0.65} threshold={0.01}>
        <section className="curriculum-hero" aria-labelledby="curriculum-title">
          <div className="curriculum-hero-copy">
            <div className="curriculum-eyebrow">
              <Compass size={15} aria-hidden="true" />
              <ShinyText
                text={`COURSE MAP · ${curriculum.version}`}
                color="var(--text-muted)"
                shineColor="var(--text-accent)"
                speed={3}
                delay={4}
                disabled={!!reduceMotion}
              />
            </div>
            <h1 id="curriculum-title" data-testid="curriculum-title">
              完整课程表
            </h1>
            <h2
              className="curriculum-hero-statement"
              aria-label="从第一行代码，走向可靠的 Agent、可控的工作流、真实的应用"
            >
              <span aria-hidden="true">从第一行代码，</span>
              <span className="curriculum-hero-line" aria-hidden="true">
                走向
                <RotatingText
                  texts={heroWords}
                  rotationInterval={3400}
                  staggerDuration={0.035}
                  mainClassName="curriculum-rotating"
                  splitLevelClassName="curriculum-rotating-word"
                />
              </span>
            </h2>
            <p className="curriculum-hero-description">
              {curriculum.title}。沿着原理、实验与工程实践，搭建属于你的 Agent
              知识地图。
            </p>
            <div className="curriculum-hero-actions">
              {firstAvailable && (
                <Button
                  className="curriculum-start-button"
                  onClick={() => onSelectLesson(firstAvailable.id)}
                >
                  从第 {firstAvailable.number} 课启程
                  <ArrowUpRight size={16} />
                </Button>
              )}
              <a href="#curriculum-domains" className="curriculum-explore-link">
                探索学习路线
                <ArrowDown size={14} />
              </a>
            </div>
          </div>
          <div className="curriculum-route-preview" aria-label="学习方式">
            <div className="curriculum-route-heading">
              <span className="curriculum-signal" />
              LEARN BY BUILDING
              <Waypoints size={16} />
            </div>
            <div className="curriculum-route-step">
              <span>
                <BookOpen size={18} />
              </span>
              <div>
                <small>01 / UNDERSTAND</small>
                <strong>把原理读懂</strong>
                <p>从真实代码开始，理解每一次模型决策。</p>
              </div>
            </div>
            <div className="curriculum-route-step">
              <span>
                <Terminal size={18} />
              </span>
              <div>
                <small>02 / EXPERIMENT</small>
                <strong>让想法运行</strong>
                <p>修改输入，亲手观察工具调用与返回。</p>
              </div>
            </div>
            <div className="curriculum-route-step">
              <span>
                <ShieldCheck size={18} />
              </span>
              <div>
                <small>03 / VERIFY</small>
                <strong>为结果找到证据</strong>
                <p>回看执行轨迹，验证结果与失败边界。</p>
              </div>
            </div>
            <div className="curriculum-route-footnote">
              <span>{availableCount} 课已开放实验</span>
              <span>
                其余内容逐课构建 <ArrowRight size={12} />
              </span>
            </div>
          </div>
        </section>
      </AnimatedContent>
      <div className="curriculum-stats">
        <MapMetric
          value={curriculum.categories.length}
          label="学习领域"
          index={0}
        />
        <MapMetric value={moduleCount} label="知识模块" index={1} />
        <MapMetric
          value={curriculum.lessons.length}
          label="主线课程"
          index={2}
        />
        <MapMetric value={availableCount} label="已可运行" index={3} />
      </div>
      <section
        className="curriculum-domains"
        id="curriculum-domains"
        aria-labelledby="curriculum-domains-title"
      >
        <div className="curriculum-section-heading">
          <div>
            <span className="curriculum-section-kicker">
              CHOOSE YOUR DIRECTION
            </span>
            <h2 id="curriculum-domains-title">每个方向，都是下一步</h2>
          </div>
          <span>点击领域，聚焦这段学习路线</span>
        </div>
        <div className="curriculum-domain-grid">
          {curriculum.categories.map((category, index) => {
            const Icon = domainIcons[index % domainIcons.length];
            const lessons = curriculum.lessons.filter(
              (lesson) => lesson.category_id === category.id,
            );
            const available = lessons.filter(
              (lesson) => lesson.status === "available",
            ).length;
            return (
              <GlareHover
                key={category.id}
                width="100%"
                height="100%"
                background="var(--surface)"
                borderColor="var(--line)"
                borderRadius="14px"
                glareColor={domainColors[index % domainColors.length]}
                glareOpacity={0.2}
                className={`curriculum-domain-glare ${activeCategory === category.id ? "is-active" : ""}`}
                style={
                  {
                    "--domain-color": domainColors[index % domainColors.length],
                  } as CSSProperties
                }
              >
                <button
                  type="button"
                  className="curriculum-domain"
                  aria-pressed={activeCategory === category.id}
                  aria-label={`筛选${category.title}`}
                  onClick={() =>
                    setActiveCategory((current) =>
                      current === category.id ? null : category.id,
                    )
                  }
                >
                  <span className="curriculum-domain-top">
                    <Icon size={20} />
                    <span>{String(index + 1).padStart(2, "0")}</span>
                  </span>
                  <strong>{category.title}</strong>
                  <span className="curriculum-domain-meta">
                    {category.modules.length} 个模块<span>·</span>
                    {lessons.length} 节课程
                  </span>
                  <span className="curriculum-domain-bottom">
                    <span className={available ? "has-available" : ""}>
                      {available ? `${available} 课可运行` : "路线已规划"}
                    </span>
                    {activeCategory === category.id ? (
                      <Check size={15} />
                    ) : (
                      <ArrowUpRight size={15} />
                    )}
                  </span>
                </button>
              </GlareHover>
            );
          })}
        </div>
      </section>
      <div className="curriculum-section-heading curriculum-results-heading">
        <div>
          <span className="curriculum-section-kicker">THE LEARNING PATH</span>
          <h2>{activeDomain ? activeDomain.title : "从起点，到完整作品"}</h2>
        </div>
        {(activeCategory || query || onlyAvailable) && (
          <button className="curriculum-reset" onClick={resetFilters}>
            <X size={13} />
            清空筛选
          </button>
        )}
      </div>
      <div
        className="panel curriculum-controls"
        data-testid="curriculum-controls"
      >
        <div className="curriculum-search">
          <label className="field-label" htmlFor="curriculum-search">
            搜索课程
          </label>
          <div>
            <Search size={16} aria-hidden="true" />
            <Input
              id="curriculum-search"
              data-testid="curriculum-search-input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索课程、知识点或实验"
            />
          </div>
        </div>
        <SquishSwitch
          className="curriculum-filter"
          label="仅显示可运行课程"
          ariaLabel="仅显示可运行课程"
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
          当前显示 {visible.length} / {curriculum.lessons.length} 课
        </span>
      </div>
      {!visible.length && (
        <div className="panel curriculum-no-results">
          <Search size={26} aria-hidden="true" />
          <h3>这段路线还没有匹配的课程</h3>
          <p>换一个关键词，或关闭领域与可运行筛选。</p>
          <Button variant="outline" onClick={resetFilters}>
            查看全部课程
          </Button>
        </div>
      )}
      {curriculum.categories.map((category, index) => {
        const modules = category.modules.filter((module) =>
          module.lesson_ids.some((id) => visibleIds.has(id)),
        );
        if (!modules.length) return null;
        return (
          <SpotlightCard
            className="panel curriculum-category"
            key={category.id}
            spotlightColor="rgba(139, 120, 230, 0.12)"
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
                {modules.length} 模块
                <ArrowDown size={13} />
              </span>
            </div>
            {modules.map((module) => (
              <div
                className="curriculum-module"
                key={module.id}
                data-testid="curriculum-module"
              >
                <div className="curriculum-module-intro">
                  <span className="curriculum-module-kicker">
                    MODULE {module.id}
                  </span>
                  <h3>{module.title}</h3>
                  <p>{module.description}</p>
                  <span className="curriculum-module-count">
                    {
                      module.lesson_ids.filter((id) => visibleIds.has(id))
                        .length
                    }{" "}
                    节课程
                    <ArrowRight size={12} />
                  </span>
                </div>
                <div className="curriculum-module-lessons">
                  {module.lesson_ids
                    .filter((id) => visibleIds.has(id))
                    .map((id) => {
                      const lesson = curriculum.lessons.find(
                        (item) => item.id === id,
                      )!;
                      return (
                        <LessonPlan
                          key={id}
                          lesson={lesson}
                          curriculum={curriculum}
                          onSelectLesson={onSelectLesson}
                        />
                      );
                    })}
                </div>
              </div>
            ))}
          </SpotlightCard>
        );
      })}
      {curriculum.electives.length > 0 && (
        <section className="panel curriculum-supplement">
          <h2>选修方向</h2>
          <p>根据你要解决的问题，选择后续学习方向。</p>
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
                  <h4>先修课程</h4>
                  <p>
                    {elective.prerequisites
                      .map(
                        (id) =>
                          curriculum.lessons.find((lesson) => lesson.id === id)
                            ?.title || id,
                      )
                      .join("；") || "无"}
                  </p>
                  <h4>知识点</h4>
                  <TextList items={elective.topics} />
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      )}
      <section className="panel curriculum-supplement curriculum-principles-panel">
        <h2>编排原则</h2>
        <TextList items={curriculum.principles} />
      </section>
      <section className="panel curriculum-supplement curriculum-sources-panel">
        <h2>参考课程与资料</h2>
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
    </div>
  );
}
