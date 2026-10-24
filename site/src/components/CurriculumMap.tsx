import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "@studio/motion";
import curriculum from "../generated/curriculum.json";
import type { Curriculum } from "../data/types";
import { Section } from "./Section";
import { Text } from "./Text";

const data = curriculum as Curriculum;
const lessonCount = (category: Curriculum["categories"][number]) =>
  category.modules.reduce((sum, module) => sum + module.lessons.length, 0);

/**
 * The curriculum as generated from curriculum/catalog.json at build time: ten domain
 * tiles, and the lessons of the chosen domain beside them.
 */
export function CurriculumMap() {
  const { t } = useTranslation("site", { keyPrefix: "curriculum" });
  const reduced = useReducedMotion();
  const [chosen, setChosen] = useState(data.categories[0].id);
  const category = data.categories.find((item) => item.id === chosen) ?? data.categories[0];
  return (
    <Section
      id="curriculum"
      eyebrow={t("eyebrow")}
      title={t("title", { count: data.lessonCount, categories: data.categories.length })}
      lead={t("lead")}
      wide
    >
      <div className="site-map">
        <div className="site-domains" role="tablist" aria-label={t("pick")}>
          {data.categories.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`domain-${item.id}`}
              aria-selected={item.id === category.id}
              aria-controls="domain-panel"
              data-testid="domain-tab"
              onClick={() => setChosen(item.id)}
            >
              <b aria-hidden="true">{item.id}</b>
              <Text value={item.title} className="site-domain-title" />
              <small>{t("count", { count: lessonCount(item) })}</small>
            </button>
          ))}
        </div>
        <div
          className="site-domain-panel"
          id="domain-panel"
          role="tabpanel"
          aria-labelledby={`domain-${category.id}`}
          data-testid="domain-panel"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={category.id}
              initial={reduced ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? {} : { opacity: 0, y: -6 }}
              transition={{ duration: reduced ? 0 : 0.22 }}
            >
              <header className="site-domain-head">
                <span className="site-domain-id" aria-hidden="true">
                  {category.id}
                </span>
                <div>
                  <Text as="h3" value={category.title} />
                  <Text as="p" value={category.description} />
                </div>
              </header>
              {category.modules.map((module) => (
                <div key={module.id} className="site-module">
                  <Text as="h4" value={module.title} />
                  <ol>
                    {module.lessons.map((lesson) => (
                      <li key={lesson.id} data-testid="curriculum-lesson" data-lesson={lesson.id}>
                        <span className="site-lesson-number">{lesson.number}</span>
                        <div>
                          <p className="site-lesson-title">
                            <Text value={lesson.title} />
                            {lesson.status !== "available" && (
                              <small>{t(`status.${lesson.status}`, lesson.status)}</small>
                            )}
                          </p>
                          <Text as="p" className="site-lesson-summary" value={lesson.summary} />
                          <p className="site-lesson-facts">
                            {lesson.level && <span>{t(`level.${lesson.level}`)}</span>}
                            {lesson.difficulty && <span>{t(`difficulty.${lesson.difficulty}`)}</span>}
                            {lesson.minutes !== null && (
                              <span>{t("minutes", { count: lesson.minutes })}</span>
                            )}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </Section>
  );
}
