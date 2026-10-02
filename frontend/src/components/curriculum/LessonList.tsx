import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { Search } from "lucide-react";
import { useReducedMotion } from "../../motion";
import type { CurriculumData } from "../../types";
import { Button } from "../ui/button";
import { CategoryBlock } from "./CategoryBlock";
import { Supplements } from "./Supplements";
import { easeOut } from "./transitions";

/** List view: matching lessons grouped by domain and module, then supplements. */
export function LessonList({
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
      {curriculum.categories.map((category, index) => (
        <CategoryBlock
          key={category.id}
          category={category}
          index={index}
          curriculum={curriculum}
          visibleIds={visibleIds}
          onSelectLesson={onSelectLesson}
        />
      ))}
      <Supplements curriculum={curriculum} />
    </>
  );
}
