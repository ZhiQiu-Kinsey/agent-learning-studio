import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { Search, X } from "lucide-react";
import { useReducedMotion } from "../../motion";
import type { CurriculumData } from "../../types";
import { Input } from "../ui/input";
import SquishSwitch from "../react-bits/SquishSwitch";
import { domainAtmosphere } from "./atmosphere";
import { easeOut, pillSpring } from "./transitions";
import type { LessonFilterState } from "./useLessonFilter";

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

/** Search box, "only available" switch, result count and domain chips. */
export function CurriculumFilters({
  curriculum,
  filter,
}: {
  curriculum: CurriculumData;
  filter: LessonFilterState;
}) {
  const { t } = useTranslation("curriculum");
  const reduced = useReducedMotion();
  const {
    query,
    setQuery,
    onlyAvailable,
    setOnlyAvailable,
    activeCategory,
    setActiveCategory,
    visibleIds,
    reset,
  } = filter;
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
          key={visibleIds.size}
          initial={reduced ? false : { opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: easeOut }}
        >
          {t("filters.count", {
            visible: visibleIds.size,
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
              onClick={reset}
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
