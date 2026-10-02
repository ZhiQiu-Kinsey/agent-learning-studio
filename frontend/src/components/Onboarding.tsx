import { Fragment, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useReducedMotion } from "../motion";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCheck,
  Clock3,
  Compass,
  ExternalLink,
  Layers3,
  Sparkles,
} from "lucide-react";
import Markdown from "react-markdown";
import { jsonFetch } from "../api";
import { chapterView } from "../content/view";
import { IllustrationFlow } from "../content/blocks/IllustrationFlow";
import { onboardingProgressId, track, useProgress } from "../progress";
import type { Onboarding as OnboardingContent } from "../content/types.gen";
import { Button } from "./ui/button";
import SplitText from "./react-bits/SplitText";
import ShinyText from "./react-bits/ShinyText";
import SpotlightCard from "./react-bits/SpotlightCard";
import AnimatedContent from "./react-bits/AnimatedContent";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./ui/accordion";

export function Onboarding({
  chapter,
  onChapterChange,
  onStart,
  onMap,
}: {
  chapter: number;
  onChapterChange: (index: number) => void;
  onStart: () => void;
  onMap: () => void;
}) {
  const [content, setContent] = useState<OnboardingContent | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  // Self-reported checkpoints persist locally; they are not a score.
  const checked =
    useProgress().lessons[onboardingProgressId]?.checkpoints ?? {};
  const reduced = useReducedMotion();
  const heroRef = useRef<HTMLElement>(null);
  const [heroActive, setHeroActive] = useState(false);
  useEffect(() => {
    if (!heroRef.current || reduced) {
      setHeroActive(false);
      return;
    }
    let visible = false;
    const update = () => setHeroActive(visible && !document.hidden);
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      update();
    });
    observer.observe(heroRef.current);
    document.addEventListener("visibilitychange", update);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", update);
    };
  }, [content, reduced]);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    jsonFetch<OnboardingContent>("/api/onboarding", {
      signal: controller.signal,
    })
      .then(setContent)
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : "读取失败");
      });
    return () => controller.abort();
  }, [attempt]);
  if (!content)
    return (
      <div className="onboarding-loading" role={error ? "alert" : "status"}>
        <Compass size={32} />
        <h1>开始你的 Agent 学习之旅</h1>
        <p>{error ? `导学内容暂时无法读取：${error}` : "正在准备学习导引…"}</p>
        {error && (
          <Button
            data-testid="onboarding-retry"
            onClick={() => setAttempt((value) => value + 1)}
          >
            重新加载导学
          </Button>
        )}
      </div>
    );
  const currentChapter = content.chapters[chapter] || content.chapters[0];
  const current = { ...currentChapter, ...chapterView(currentChapter) };
  const illustrations = currentChapter.illustrations;
  const completed = content.chapters.filter((item) =>
    chapterView(item).exercise.checkpoints.every(
      (point) => checked[`${item.id}/${point.id}`],
    ),
  ).length;
  function navigate(index: number) {
    onChapterChange(index);
    window.scrollTo({ top: 0, behavior: reduced ? "instant" : "smooth" });
  }
  return (
    <div className="onboarding-page" data-testid="onboarding-page">
      <section
        ref={heroRef}
        data-testid="onboarding-hero"
        className={`onboarding-hero ${heroActive ? "is-animating" : ""}`}
      >
        <div className="onboarding-hero-grid" aria-hidden="true" />
        <div className="onboarding-hero-copy">
          <span className="onboarding-eyebrow">
            <Sparkles size={13} />
            <ShinyText
              text="A FIELD GUIDE TO BUILDING AGENTS"
              speed={4}
              delay={2}
              disabled={!!reduced}
              color="var(--accent)"
              shineColor="var(--cyan)"
            />
          </span>
          {reduced ? (
            <h1>先理解 Agent，再亲手构建。</h1>
          ) : (
            <SplitText
              text="先理解 Agent，再亲手构建。"
              tag="h1"
              splitType="chars"
              textAlign="left"
              delay={35}
              duration={0.65}
              from={{ opacity: 0, y: 25, rotateX: -35 }}
              to={{ opacity: 1, y: 0, rotateX: 0 }}
            />
          )}
          <p>{content.description}</p>
          <div className="onboarding-hero-actions">
            <Button
              onClick={() =>
                document
                  .getElementById("onboarding-chapter")
                  ?.scrollIntoView({ behavior: reduced ? "instant" : "smooth" })
              }
            >
              从这里开始 <ArrowRight size={16} />
            </Button>
            <Button variant="ghost" onClick={onMap}>
              <Layers3 size={15} />
              探索完整课程
            </Button>
          </div>
          <div className="onboarding-meta" data-testid="onboarding-meta">
            <span>
              <BookOpen size={14} />
              {content.chapters.length} 节前置导学
            </span>
            <span>
              <Clock3 size={14} />约{" "}
              {content.chapters.reduce(
                (sum, item) => sum + item.estimated_minutes,
                0,
              )}{" "}
              分钟
            </span>
            <span>
              <CheckCheck size={14} />
              {completed} 节已自检
            </span>
          </div>
        </div>
        <div className="onboarding-orbit" aria-hidden="true">
          <div className="orbit-ring orbit-ring-one" />
          <div className="orbit-ring orbit-ring-two" />
          <div className="orbit-ring orbit-ring-three" />
          <div className="orbit-core">
            <Compass size={44} />
            <span>AGENT</span>
            <small>LEARN · BUILD · VERIFY</small>
          </div>
          <span className="orbit-label orbit-label-a">模型 · 决策</span>
          <span className="orbit-label orbit-label-b">工具 · 行动</span>
          <span className="orbit-label orbit-label-c">证据 · 验证</span>
          <i className="orbit-signal" />
        </div>
      </section>
      <nav
        className="onboarding-chapter-tabs"
        aria-label="前置导学章节"
        data-testid="onboarding-chapter-tabs"
      >
        {content.chapters.map((item, index) => (
          <button
            type="button"
            key={item.id}
            className={chapter === index ? "is-active" : ""}
            aria-current={chapter === index ? "step" : undefined}
            onClick={() => navigate(index)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{item.title}</strong>
            <small>{item.estimated_minutes} 分钟</small>
            {chapter === index && (
              <motion.i
                layoutId="onboarding-chapter"
                transition={{ duration: reduced ? 0 : 0.3 }}
              />
            )}
          </button>
        ))}
      </nav>
      <div className="onboarding-reading-layout" id="onboarding-chapter">
        <AnimatePresence mode="wait" initial={false}>
          <motion.article
            key={current.id}
            className="onboarding-chapter"
            data-testid="onboarding-chapter"
            initial={reduced ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? {} : { opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <header>
              <span className="onboarding-eyebrow">{current.eyebrow}</span>
              <h2>{current.title}</h2>
              <p>{current.summary}</p>
            </header>
            {current.sections.map((section, index) => (
              <Fragment key={section.id}>
                <AnimatedContent
                  key={section.id}
                  distance={18}
                  duration={0.5}
                  threshold={0.05}
                >
                  <section
                    className={`onboarding-section onboarding-section-${section.kind}`}
                    data-testid="onboarding-section"
                  >
                    <h3>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      {section.title}
                    </h3>
                    {section.paragraphs.map((paragraph, i) => (
                      <div className="onboarding-prose" key={i}>
                        <Markdown>{paragraph}</Markdown>
                      </div>
                    ))}
                    {!!section.bullets?.length && (
                      <ul>
                        {section.bullets.map((bullet, i) => (
                          <li key={i}>
                            <Markdown>{bullet}</Markdown>
                          </li>
                        ))}
                      </ul>
                    )}
                    {section.table && (
                      <div className="onboarding-table">
                        <table>
                          <thead>
                            <tr>
                              {section.table.columns.map((column) => (
                                <th key={column}>{column}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {section.table.rows.map((row, i) => (
                              <tr key={i}>
                                {row.map((cell, j) => (
                                  <td key={j}>
                                    <Markdown>{cell}</Markdown>
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>
                </AnimatedContent>
                {current.flows
                  .filter((flow) => flow.after === section.id)
                  .map(({ block }) =>
                    illustrations[block.illustration] ? (
                      <IllustrationFlow
                        key={block.id}
                        block={block}
                        illustration={illustrations[block.illustration]}
                      />
                    ) : null,
                  )}
              </Fragment>
            ))}
            <section className="onboarding-exercise">
              <div className="onboarding-eyebrow">
                <CheckCheck size={15} />
                停下来，想一想
              </div>
              <h3>{current.exercise.title}</h3>
              <p>{current.exercise.prompt}</p>
              <div
                className="onboarding-checks"
                data-testid="onboarding-checks"
              >
                {current.exercise.checkpoints.map((point) => {
                  const id = `${current.id}/${point.id}`;
                  return (
                    <label key={id}>
                      <input
                        type="checkbox"
                        checked={!!checked[id]}
                        onChange={(e) =>
                          track.checkpointSet(
                            onboardingProgressId,
                            id,
                            e.target.checked,
                          )
                        }
                      />
                      <span
                        className="onboarding-check-icon"
                        aria-hidden="true"
                      >
                        {checked[id] && <Check size={13} />}
                      </span>
                      <span>{point.text}</span>
                    </label>
                  );
                })}
              </div>
              <small>勾选用于确认自己的理解，不是自动评分。</small>
            </section>
            <Accordion
              type="single"
              collapsible
              className="onboarding-sources"
              data-testid="onboarding-sources"
            >
              <AccordionItem value="sources">
                <AccordionTrigger>
                  这一章参考了什么 · {current.references.length} 份资料
                </AccordionTrigger>
                <AccordionContent>
                  <ul>
                    {current.references.map((reference) => (
                      <li key={reference.url}>
                        <a
                          href={reference.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {reference.title}
                          <ExternalLink size={12} />
                        </a>
                      </li>
                    ))}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
            <div className="onboarding-next">
              <Button
                variant="ghost"
                disabled={chapter === 0}
                onClick={() => navigate(chapter - 1)}
              >
                <ArrowLeft size={15} />
                上一节
              </Button>
              <Button
                data-testid="onboarding-next"
                onClick={() =>
                  chapter < content.chapters.length - 1
                    ? navigate(chapter + 1)
                    : onStart()
                }
              >
                {chapter < content.chapters.length - 1
                  ? `继续：${content.chapters[chapter + 1].title}`
                  : "开始第 1 课：工具选择"}
                <ArrowRight size={15} />
              </Button>
            </div>
          </motion.article>
        </AnimatePresence>
        <aside className="onboarding-aside">
          <SpotlightCard
            className="onboarding-objectives"
            spotlightColor="rgba(122, 100, 240, 0.15)"
          >
            <Compass size={25} />
            <h3>读完这一节，你将理解</h3>
            <ul>
              {current.objectives.map((item) => (
                <li key={item}>
                  <Check size={14} />
                  {item}
                </li>
              ))}
            </ul>
          </SpotlightCard>
          <div className="onboarding-aside-note">
            <span>你的学习节奏</span>
            <p>先建立概念，再读代码。每一次实验，都带着一个想验证的问题。</p>
            <Button variant="link" onClick={onStart}>
              已做好准备，进入第 1 课 <ArrowRight size={14} />
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}
