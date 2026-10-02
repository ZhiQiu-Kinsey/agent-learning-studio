import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { revealProps, useMotionBudget, useReducedMotion } from "../motion";
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
  ListChecks,
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
import StarBorder from "./react-bits/StarBorder";
import SpringCheck from "./react-bits/SpringCheck";
import { Backdrop } from "./backdrops/Backdrop";
import type { BackdropName } from "./backdrops/presets";
import { backdropAccent } from "./curriculum/atmosphere";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./ui/accordion";

const easeOut = [0.16, 1, 0.3, 1] as const;
const tabSpring = { type: "spring", stiffness: 380, damping: 32 } as const;

/** Every chapter has its own sky; unknown chapters cycle through the list. */
const chapterSkies: Record<string, BackdropName> = {
  intro: "aurora",
  "what-is-agent": "web",
  "learning-path": "rays",
  "lab-evidence": "radar",
};
const skyCycle: BackdropName[] = ["aurora", "web", "rays", "radar", "veil"];
const skyFor = (id: string, index: number): BackdropName =>
  chapterSkies[id] ?? skyCycle[index % skyCycle.length];

/** Chapter heading: characters rise out of a blur; spaces stay real text. */
function RevealTitle({ text }: { text: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <>{text}</>;
  let index = 0;
  return (
    <>
      {text.split(/(\s+)/).map((part, word) =>
        /^\s+$/.test(part) ? (
          part
        ) : (
          <span className="onboarding-title-word" key={word}>
            {Array.from(part).map((char) => {
              const delay = 0.12 + index++ * 0.035;
              return (
                <motion.span
                  key={index}
                  className="onboarding-title-char"
                  initial={{ opacity: 0, y: "0.45em", filter: "blur(10px)" }}
                  animate={{
                    opacity: 1,
                    y: 0,
                    filter: "blur(0px)",
                    transitionEnd: { filter: "none" },
                  }}
                  transition={{ duration: 0.6, delay, ease: easeOut }}
                >
                  {char}
                </motion.span>
              );
            })}
          </span>
        ),
      )}
    </>
  );
}

/** Scroll reveal for reading blocks; static motion shows them as they are. */
function Reveal({
  children,
  className,
  delay = 0,
  as = "div",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "section";
  [data: `data-${string}`]: string | undefined;
}) {
  const reduced = useReducedMotion();
  const Tag = as === "section" ? motion.section : motion.div;
  return (
    <Tag
      className={className}
      {...rest}
      {...revealProps(
        reduced,
        { opacity: 0, y: 22, filter: "blur(6px)" },
        { opacity: 1, y: 0, filter: "blur(0px)", transitionEnd: { filter: "none" } },
        { duration: 0.6, delay, ease: easeOut },
      )}
      viewport={{ once: true, amount: 0.12 }}
    >
      {children}
    </Tag>
  );
}

function OnboardingHero({
  content,
  completed,
  onMap,
}: {
  content: OnboardingContent;
  completed: number;
  onMap: () => void;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const reduced = useReducedMotion();
  // CSS orbit loops run only while the hero is on screen in a visible tab.
  const { ref, active } = useMotionBudget<HTMLElement>("css");
  const minutes = content.chapters.reduce(
    (sum, item) => sum + item.estimated_minutes,
    0,
  );
  const rise = (step: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: 16, filter: "blur(8px)" },
          animate: {
            opacity: 1,
            y: 0,
            filter: "blur(0px)",
            transitionEnd: { filter: "none" },
          },
          transition: {
            duration: 0.7,
            delay: 0.25 + step * 0.1,
            ease: easeOut,
          },
        };
  return (
    <section
      ref={ref}
      data-testid="onboarding-hero"
      className={`onboarding-hero ${active ? "is-animating" : ""}`}
    >
      <div className="onboarding-hero-grid" aria-hidden="true" />
      <div className="onboarding-hero-copy">
        <motion.span className="onboarding-eyebrow" {...rise(-1)}>
          <Sparkles size={13} aria-hidden="true" />
          <ShinyText
            text={t("eyebrow")}
            speed={4}
            delay={2}
            disabled={!!reduced}
            color="#8ff0de"
            shineColor="#ffffff"
          />
        </motion.span>
        {reduced ? (
          <h1>{t("title")}</h1>
        ) : (
          <SplitText
            text={t("title")}
            tag="h1"
            splitType="chars"
            textAlign="left"
            delay={35}
            duration={0.65}
            from={{ opacity: 0, y: 25, rotateX: -35 }}
            to={{ opacity: 1, y: 0, rotateX: 0 }}
          />
        )}
        <motion.p {...rise(1)}>{content.description}</motion.p>
        <motion.div className="onboarding-hero-actions" {...rise(2)}>
          <StarBorder
            className="onboarding-start-star"
            color="#49dec6"
            speed="6s"
          >
            <Button
              className="onboarding-start-button"
              onClick={() =>
                document
                  .getElementById("onboarding-chapter")
                  ?.scrollIntoView({ behavior: reduced ? "instant" : "smooth" })
              }
            >
              {t("start")} <ArrowRight size={16} />
            </Button>
          </StarBorder>
          <Button
            variant="ghost"
            className="onboarding-map-button"
            onClick={onMap}
          >
            <Layers3 size={15} />
            {t("explore")}
          </Button>
        </motion.div>
        <motion.div
          className="onboarding-meta"
          data-testid="onboarding-meta"
          {...rise(3)}
        >
          <span>
            <BookOpen size={14} />
            {t("metaChapters", { n: content.chapters.length })}
          </span>
          <span>
            <Clock3 size={14} />
            {t("metaMinutes", { n: minutes })}
          </span>
          <span>
            <CheckCheck size={14} />
            {t("metaChecked", { n: completed })}
          </span>
        </motion.div>
      </div>
      <div className="onboarding-orbit" aria-hidden="true">
        <div className="orbit-ring orbit-ring-one" />
        <div className="orbit-ring orbit-ring-two" />
        <div className="orbit-ring orbit-ring-three" />
        <div className="onboarding-orb">
          <Backdrop
            name="orb"
            className="onboarding-orb-shader is-interactive"
          />
        </div>
        <div className="orbit-core">
          <span>{t("core")}</span>
          <small>{t("coreTagline")}</small>
        </div>
        <span className="orbit-label orbit-label-a">{t("orbitModel")}</span>
        <span className="orbit-label orbit-label-b">{t("orbitTool")}</span>
        <span className="orbit-label orbit-label-c">{t("orbitEvidence")}</span>
        <i className="orbit-signal" />
      </div>
    </section>
  );
}

/** Thin ring showing how many checkpoints of a chapter were self-reported. */
function CheckRing({ done, total }: { done: number; total: number }) {
  const ratio = total ? done / total : 0;
  return (
    <svg className="onboarding-tab-ring" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="8" pathLength={1} />
      <circle
        cx="10"
        cy="10"
        r="8"
        pathLength={1}
        strokeDasharray={1}
        style={{ strokeDashoffset: 1 - ratio }}
      />
    </svg>
  );
}

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
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const [content, setContent] = useState<OnboardingContent | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  // Self-reported checkpoints persist locally; they are not a score.
  const checked =
    useProgress().lessons[onboardingProgressId]?.checkpoints ?? {};
  const reduced = useReducedMotion();
  // Direction of the last chapter change, for the slide of the transition.
  const previous = useRef(chapter);
  const direction = chapter >= previous.current ? 1 : -1;
  useEffect(() => {
    previous.current = chapter;
  }, [chapter]);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    jsonFetch<OnboardingContent>("/api/onboarding", {
      signal: controller.signal,
    })
      .then(setContent)
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : t("readFailed"));
      });
    return () => controller.abort();
  }, [attempt, t]);
  if (!content)
    return (
      <div className="onboarding-loading" role={error ? "alert" : "status"}>
        <Compass size={32} />
        <h1>{t("loadingTitle")}</h1>
        <p>{error ? t("loadFailed", { reason: error }) : t("loading")}</p>
        {error && (
          <Button
            data-testid="onboarding-retry"
            onClick={() => setAttempt((value) => value + 1)}
          >
            {t("retry")}
          </Button>
        )}
      </div>
    );
  const chapterIndex = content.chapters[chapter] ? chapter : 0;
  const currentChapter = content.chapters[chapterIndex];
  const current = { ...currentChapter, ...chapterView(currentChapter) };
  const illustrations = currentChapter.illustrations;
  const checksOf = (item: (typeof content.chapters)[number]) => {
    const points = chapterView(item).exercise.checkpoints;
    return {
      total: points.length,
      done: points.filter((point) => checked[`${item.id}/${point.id}`]).length,
    };
  };
  const completed = content.chapters.filter((item) => {
    const { done, total } = checksOf(item);
    return done === total;
  }).length;
  const currentChecks = checksOf(currentChapter);
  const chapterDone =
    currentChecks.total > 0 && currentChecks.done === currentChecks.total;
  const sky = skyFor(current.id, chapterIndex);
  const accent = backdropAccent(sky);
  function navigate(index: number) {
    onChapterChange(index);
    window.scrollTo({ top: 0, behavior: reduced ? "instant" : "smooth" });
  }
  const offset = 46 * direction;
  return (
    <div className="onboarding-page" data-testid="onboarding-page">
      <OnboardingHero content={content} completed={completed} onMap={onMap} />
      <nav
        className="onboarding-chapter-tabs"
        aria-label={t("tabsLabel")}
        data-testid="onboarding-chapter-tabs"
      >
        {content.chapters.map((item, index) => {
          const { done, total } = checksOf(item);
          const active = chapterIndex === index;
          return (
            <button
              type="button"
              key={item.id}
              className={active ? "is-active" : ""}
              aria-current={active ? "step" : undefined}
              data-complete={total > 0 && done === total}
              style={
                {
                  "--tab-rgb": backdropAccent(skyFor(item.id, index)),
                } as CSSProperties
              }
              onClick={() => navigate(index)}
            >
              {active && (
                <motion.i
                  className="onboarding-tab-pill"
                  layoutId="onboarding-chapter"
                  transition={reduced ? { duration: 0 } : tabSpring}
                  aria-hidden="true"
                />
              )}
              <span className="onboarding-tab-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <strong>{item.title}</strong>
              <small>{t("minutes", { n: item.estimated_minutes })}</small>
              <span className="onboarding-tab-checks">
                <CheckRing done={done} total={total} />
                <span className="sr-only">
                  {t("tabChecks", { done, total })}
                </span>
              </span>
            </button>
          );
        })}
      </nav>
      <div className="onboarding-reading-layout" id="onboarding-chapter">
        <AnimatePresence mode="wait" initial={false}>
          <motion.article
            key={current.id}
            className="onboarding-chapter"
            data-testid="onboarding-chapter"
            style={{ "--chapter-rgb": accent } as CSSProperties}
            initial={
              reduced ? false : { opacity: 0, x: offset, filter: "blur(14px)" }
            }
            animate={{
              opacity: 1,
              x: 0,
              filter: "blur(0px)",
              transitionEnd: { filter: "none" },
            }}
            exit={
              reduced
                ? {}
                : {
                    opacity: 0,
                    x: -offset * 0.6,
                    filter: "blur(10px)",
                    transition: { duration: 0.22, ease: [0.4, 0, 1, 1] },
                  }
            }
            transition={{ duration: 0.5, ease: easeOut }}
          >
            <header className="onboarding-chapter-band">
              <Backdrop name={sky} className="onboarding-band-backdrop" />
              <div className="onboarding-band-scrim" aria-hidden="true" />
              <span className="onboarding-band-numeral" aria-hidden="true">
                {String(chapterIndex + 1).padStart(2, "0")}
              </span>
              <div className="onboarding-band-copy">
                <span className="onboarding-eyebrow">
                  <span className="onboarding-band-dot" aria-hidden="true" />
                  {current.eyebrow}
                </span>
                <h2>
                  <RevealTitle text={current.title} />
                </h2>
                <motion.p
                  initial={reduced ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.35, ease: easeOut }}
                >
                  {current.summary}
                </motion.p>
                <motion.div
                  className="onboarding-band-chips"
                  initial={reduced ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.45, ease: easeOut }}
                >
                  <span>
                    {t("chapterIndex", {
                      index: chapterIndex + 1,
                      total: content.chapters.length,
                    })}
                  </span>
                  <span>
                    <Clock3 size={13} aria-hidden="true" />
                    {t("minutes", { n: current.estimated_minutes })}
                  </span>
                  <span>
                    <ListChecks size={13} aria-hidden="true" />
                    {t("sections", { n: current.sections.length })}
                  </span>
                </motion.div>
              </div>
            </header>
            <div className="onboarding-chapter-body">
              {current.sections.map((section, index) => (
                <Fragment key={section.id}>
                  <Reveal
                    as="section"
                    className={`onboarding-section onboarding-section-${section.kind}`}
                    data-testid="onboarding-section"
                  >
                    <h3>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      {section.title}
                    </h3>
                    {section.paragraphs.map((paragraph, i) => (
                      <Reveal
                        className="onboarding-prose"
                        key={i}
                        delay={Math.min(i, 3) * 0.06}
                      >
                        <Markdown>{paragraph}</Markdown>
                      </Reveal>
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
                  </Reveal>
                  {current.flows
                    .filter((flow) => flow.after === section.id)
                    .map(({ block }) =>
                      illustrations[block.illustration] ? (
                        <Reveal key={block.id} className="onboarding-flow">
                          <IllustrationFlow
                            block={block}
                            illustration={illustrations[block.illustration]}
                          />
                        </Reveal>
                      ) : null,
                    )}
                </Fragment>
              ))}
              <Reveal
                as="section"
                className="onboarding-exercise"
                data-complete={chapterDone ? "true" : "false"}
              >
                <div className="onboarding-exercise-head">
                  <span className="onboarding-eyebrow">
                    <CheckCheck size={15} aria-hidden="true" />
                    {t("pause")}
                  </span>
                  <AnimatePresence>
                    {chapterDone && (
                      <motion.span
                        className="onboarding-exercise-badge"
                        initial={reduced ? false : { opacity: 0, scale: 0.6 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={reduced ? undefined : { opacity: 0, scale: 0.8 }}
                        transition={
                          reduced
                            ? { duration: 0 }
                            : { type: "spring", stiffness: 500, damping: 22 }
                        }
                      >
                        <Check size={13} aria-hidden="true" />
                        {t("chapterChecked")}
                      </motion.span>
                    )}
                  </AnimatePresence>
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
                      <SpringCheck
                        key={id}
                        className="onboarding-check"
                        label={point.text}
                        checked={!!checked[id]}
                        onChange={(value) =>
                          track.checkpointSet(onboardingProgressId, id, value)
                        }
                      />
                    );
                  })}
                </div>
                <small>{t("checkNote")}</small>
              </Reveal>
              <Accordion
                type="single"
                collapsible
                className="onboarding-sources"
                data-testid="onboarding-sources"
              >
                <AccordionItem value="sources">
                  <AccordionTrigger>
                    {t("sources", { n: current.references.length })}
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
                  disabled={chapterIndex === 0}
                  onClick={() => navigate(chapterIndex - 1)}
                >
                  <ArrowLeft size={15} />
                  {t("previous")}
                </Button>
                <Button
                  data-testid="onboarding-next"
                  className="onboarding-next-button"
                  onClick={() =>
                    chapterIndex < content.chapters.length - 1
                      ? navigate(chapterIndex + 1)
                      : onStart()
                  }
                >
                  {chapterIndex < content.chapters.length - 1
                    ? t("next", {
                        title: content.chapters[chapterIndex + 1].title,
                      })
                    : t("startLesson")}
                  <ArrowRight size={15} />
                </Button>
              </div>
            </div>
          </motion.article>
        </AnimatePresence>
        <aside className="onboarding-aside">
          <SpotlightCard
            className="onboarding-objectives"
            spotlightColor="rgba(122, 100, 240, 0.15)"
          >
            <Compass size={25} />
            <h3>{t("objectives")}</h3>
            <ul key={current.id}>
              {current.objectives.map((item, index) => (
                <motion.li
                  key={item}
                  initial={reduced ? false : { opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{
                    duration: 0.45,
                    delay: 0.2 + index * 0.08,
                    ease: easeOut,
                  }}
                >
                  <Check size={14} />
                  {item}
                </motion.li>
              ))}
            </ul>
          </SpotlightCard>
          <div className="onboarding-aside-note">
            <span>{t("paceTitle")}</span>
            <p>{t("paceBody")}</p>
            <Button variant="link" onClick={onStart}>
              {t("ready")} <ArrowRight size={14} />
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}
