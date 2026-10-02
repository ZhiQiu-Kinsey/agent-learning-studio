import type { ReactNode } from "react";
import Markdown from "react-markdown";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Braces, Cpu, Eye, Network, Quote } from "lucide-react";
import { useReducedMotion } from "../../motion";
import type { Detail, Trace } from "../../types";
import SpotlightCard from "../../components/react-bits/SpotlightCard";
import ScrollReveal from "../../components/react-bits/ScrollReveal";
import FadeContent from "../../components/react-bits/FadeContent";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";
import { AgentFlow } from "../../components/learning/AgentFlow";
import { sceneBlocks, type Block } from "../view";
import { MicroQuizBlock } from "./MicroQuizBlock";
import { PredictBlock } from "./PredictBlock";
import { IllustrationFlow } from "./IllustrationFlow";
import {
  CalloutBlock,
  CompareBlock,
  MisconceptionBlock,
  ReferencesBlock,
  StepsBlock,
} from "./basic";

const conceptIcons = [Braces, Cpu, Network];

/**
 * 理解 scene body: blocks render in the order the lesson authored them.
 * The hero is shown by LessonHero above; its takeaway follows the concepts.
 */
export function UnderstandBlocks({
  detail,
  events,
  onRun,
}: {
  detail: Detail;
  events: readonly Trace[];
  onRun: () => void;
}) {
  const { t } = useTranslation("blocks");
  const reduced = useReducedMotion();
  const content = detail.learning;
  const blocks = sceneBlocks(content, "understand");
  const hero = blocks.find((block) => block.type === "hero");
  const observe =
    content?.scenes.lab?.experiments.flatMap((item) => item.observe) ?? [];
  let section = 0;
  const reveal = (key: string, node: ReactNode) => (
    <FadeContent key={key} className="block-reveal">
      {node}
    </FadeContent>
  );

  const render = (block: Block) => {
    switch (block.type) {
      case "concepts":
        return (
          <div key={block.id}>
            <section
              className="learn-concepts"
              aria-label={t("concepts.region")}
              data-testid="block-concepts"
            >
              <div className="learn-section-kicker">
                <span>{block.title ?? "CONNECT THE IDEAS"}</span>
                <span>{t("concepts.kicker")}</span>
              </div>
              <div className="learn-concept-grid">
                {block.items.map((concept, index) => {
                  const Icon = conceptIcons[index % conceptIcons.length];
                  return (
                    <FadeContent
                      className="learn-concept-cell"
                      key={concept.id}
                      delay={index * 0.12}
                      distance={28}
                    >
                      <SpotlightCard
                        className="learn-concept"
                        spotlightColor="rgba(135, 110, 240, 0.22)"
                      >
                        <div className="learn-concept-top">
                          <span>
                            <Icon size={18} />
                          </span>
                          <small>{concept.label}</small>
                        </div>
                        <h3>{concept.title}</h3>
                        <p>{concept.description}</p>
                        {concept.token && <code>{concept.token}</code>}
                      </SpotlightCard>
                    </FadeContent>
                  );
                })}
              </div>
            </section>
            {hero?.takeaway && (
              <FadeContent
                as="aside"
                className="lesson-takeaway"
                aria-label={t("takeaway.region")}
              >
                <Quote size={24} aria-hidden="true" />
                <div>
                  <span>{t("takeaway.label")}</span>
                  <ScrollReveal>{hero.takeaway}</ScrollReveal>
                </div>
              </FadeContent>
            )}
          </div>
        );
      case "prose": {
        section += 1;
        return (
          <motion.section
            className="reading-section"
            data-testid="learn-reading-section"
            key={block.id}
            initial={
              reduced ? false : { opacity: 0.35, y: 22, filter: "blur(6px)" }
            }
            whileInView={
              reduced ? undefined : { opacity: 1, y: 0, filter: "blur(0px)" }
            }
            viewport={{ once: true, amount: 0.08 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="reading-section-heading">
              <span aria-hidden="true">{String(section).padStart(2, "0")}</span>
              {block.title && <h2>{block.title}</h2>}
            </div>
            <div className="reading-prose">
              {block.paragraphs.map((paragraph, index) => (
                <Markdown key={index}>{paragraph}</Markdown>
              ))}
            </div>
          </motion.section>
        );
      }
      case "walkthrough":
        return reveal(block.id, <AgentFlow flow={block} />);
      case "flow": {
        const illustration = content?.illustrations[block.illustration];
        return illustration
          ? reveal(
              block.id,
              <IllustrationFlow block={block} illustration={illustration} />,
            )
          : null;
      }
      case "micro-quiz":
        return reveal(block.id, <MicroQuizBlock block={block} />);
      case "predict":
        return reveal(
          block.id,
          <PredictBlock
            block={block}
            lessonId={detail.id}
            events={events}
            onRun={onRun}
          />,
        );
      case "steps":
        return reveal(block.id, <StepsBlock block={block} />);
      case "compare":
        return reveal(block.id, <CompareBlock block={block} />);
      case "callout":
        return reveal(block.id, <CalloutBlock block={block} />);
      case "misconception":
        return reveal(block.id, <MisconceptionBlock block={block} />);
      case "references":
        return reveal(block.id, <ReferencesBlock block={block} />);
      default:
        return null; // hero is rendered by LessonHero; scene-specific blocks live in their scenes
    }
  };

  return (
    <div className="lesson-guide">
      <article
        className="reading-document"
        aria-label={t("reading.region")}
        data-testid="learn-reading-document"
      >
        {blocks.map(render)}
        {!blocks.some((block) => block.type === "prose") && (
          <p className="reading-prose">{t("reading.empty")}</p>
        )}
        {observe.length > 0 && (
          <Accordion
            type="single"
            collapsible
            defaultValue="observe"
            className="reading-observations"
            data-testid="learn-observations"
          >
            <AccordionItem value="observe">
              <AccordionTrigger>
                <span>
                  <Eye size={16} />
                  {t("observe.title")}
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <ol>
                  {observe.map((point) => (
                    <li key={point.id}>{point.text}</li>
                  ))}
                </ol>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        )}
      </article>
    </div>
  );
}
