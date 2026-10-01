import Markdown from "react-markdown";
import { motion } from "motion/react";
import { useReducedMotion } from "../../motion";
import { Braces, Cpu, Eye, Network, Quote } from "lucide-react";
import type { Detail } from "../../types";
import SpotlightCard from "../react-bits/SpotlightCard";
import ScrollReveal from "../react-bits/ScrollReveal";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../ui/accordion";
import { AgentFlow } from "./AgentFlow";
import { lessonView } from "../../content/view";

const conceptIcons = [Braces, Cpu, Network];

export function LessonGuide({ detail }: { detail: Detail }) {
  const reduced = useReducedMotion();
  const view = lessonView(detail.learning);
  const presentation = view.hero;
  return (
    <div className="lesson-guide">
      {presentation && (
        <>
          {view.walkthrough && (
            <AgentFlow key={detail.id} flow={view.walkthrough} />
          )}
          <section className="learn-concepts" aria-label="核心概念速览">
            <div className="learn-section-kicker">
              <span>02 / CONNECT THE IDEAS</span>
              <span>把关键关系记清楚</span>
            </div>
            <div className="learn-concept-grid">
              {view.concepts.map((concept, index) => {
                const Icon = conceptIcons[index % conceptIcons.length];
                return (
                  <SpotlightCard
                    className="learn-concept"
                    key={concept.id}
                    spotlightColor="rgba(135, 110, 240, 0.16)"
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
                );
              })}
            </div>
          </section>
          <aside className="lesson-takeaway" aria-label="本课关键思路">
            <Quote size={24} aria-hidden="true" />
            <div>
              <span>记住这个思路</span>
              <ScrollReveal>{presentation.takeaway ?? ""}</ScrollReveal>
            </div>
          </aside>
        </>
      )}
      <article className="reading-document" aria-label="课程导读">
        {presentation && (
          <div className="learn-section-kicker">
            <span>03 / GO A LITTLE DEEPER</span>
            <span>逐层理解，保留每一处细节</span>
          </div>
        )}
        {view.sections.map((section, index) => (
          <motion.section
            className="reading-section"
            key={section.id}
            initial={reduced ? false : { opacity: 0.65, y: 14 }}
            animate={reduced ? { opacity: 1, y: 0 } : undefined}
            whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.1 }}
            transition={{ duration: reduced ? 0 : 0.4 }}
          >
            <div className="reading-section-heading">
              <span aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              {section.title && <h2>{section.title}</h2>}
            </div>
            <div className="reading-prose">
              {section.paragraphs.map((paragraph, paragraphIndex) => (
                <Markdown key={paragraphIndex}>{paragraph}</Markdown>
              ))}
            </div>
          </motion.section>
        ))}
        {!view.sections.length && (
          <p className="reading-prose">
            从右侧学习目标出发，阅读本课 Python
            源码，再进入实验工作台观察运行过程。
          </p>
        )}
        {!!view.observe.length && (
          <Accordion
            type="single"
            collapsible
            defaultValue="observe"
            className="reading-observations"
          >
            <AccordionItem value="observe">
              <AccordionTrigger>
                <span>
                  <Eye size={16} />
                  运行时，留意这些观察点
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <ol>
                  {view.observe.map((point) => (
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
