import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { ArrowDown, ArrowRight } from "lucide-react";
import { revealProps, useReducedMotion } from "../../motion";
import type { CurriculumData } from "../../types";
import SpotlightCard from "../react-bits/SpotlightCard";
import { domainAtmosphere } from "./atmosphere";
import { useResolvedTheme } from "../../hooks/useTheme";
import { LessonPlan } from "./LessonPlan";
import { easeOut } from "./transitions";

type CurriculumCategory = CurriculumData["categories"][number];
type CurriculumModule = CurriculumCategory["modules"][number];

/** A lesson row sliding in on scroll and out when a filter hides it. */
function LessonRow({
  id,
  row,
  curriculum,
  onSelectLesson,
}: {
  id: string;
  row: number;
  curriculum: CurriculumData;
  onSelectLesson: (id: string) => void;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className="curriculum-lesson-row"
      {...revealProps(
        reduced,
        { opacity: 0, x: -14, filter: "blur(6px)" },
        {
          opacity: 1,
          x: 0,
          filter: "blur(0px)",
          transitionEnd: { filter: "none" },
        },
        {
          duration: 0.45,
          delay: Math.min(row, 8) * 0.045,
          ease: easeOut,
        },
      )}
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
    >
      <LessonPlan
        lesson={curriculum.lessons.find((item) => item.id === id)!}
        curriculum={curriculum}
        onSelectLesson={onSelectLesson}
      />
    </motion.div>
  );
}

function ModuleBlock({
  module,
  ids,
  curriculum,
  onSelectLesson,
}: {
  module: CurriculumModule;
  ids: string[];
  curriculum: CurriculumData;
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  return (
    <div className="curriculum-module" data-testid="curriculum-module">
      <div className="curriculum-module-intro">
        <span className="curriculum-module-kicker">
          {t("list.moduleKicker", { id: module.id })}
        </span>
        <h3>{module.title}</h3>
        <p>{module.description}</p>
        <span className="curriculum-module-count">
          {t("list.lessons", { count: ids.length })}
          <ArrowRight size={12} />
        </span>
      </div>
      <div className="curriculum-module-lessons">
        <AnimatePresence initial={!reduced}>
          {ids.map((id, row) => (
            <LessonRow
              key={id}
              id={id}
              row={row}
              curriculum={curriculum}
              onSelectLesson={onSelectLesson}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

/** One domain of the list view with its modules, showing only matching lessons. */
export function CategoryBlock({
  category,
  index,
  curriculum,
  visibleIds,
  onSelectLesson,
}: {
  category: CurriculumCategory;
  index: number;
  curriculum: CurriculumData;
  visibleIds: ReadonlySet<string>;
  onSelectLesson: (id: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  const theme = useResolvedTheme();
  const modules = category.modules.filter((module) =>
    module.lesson_ids.some((id) => visibleIds.has(id)),
  );
  if (!modules.length) return null;
  const { accent } = domainAtmosphere(category.id, theme);
  return (
    <motion.div
      className="curriculum-category-reveal"
      style={{ "--domain-rgb": accent } as CSSProperties}
      {...revealProps(
        reduced,
        { opacity: 0, y: 28 },
        { opacity: 1, y: 0 },
        { duration: 0.6, ease: easeOut },
      )}
      viewport={{ once: true, amount: 0.04 }}
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
            {t("list.modules", { count: modules.length })}
            <ArrowDown size={13} />
          </span>
        </div>
        {modules.map((module) => (
          <ModuleBlock
            key={module.id}
            module={module}
            ids={module.lesson_ids.filter((id) => visibleIds.has(id))}
            curriculum={curriculum}
            onSelectLesson={onSelectLesson}
          />
        ))}
      </SpotlightCard>
    </motion.div>
  );
}
