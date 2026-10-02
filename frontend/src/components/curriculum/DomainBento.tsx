import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowUpRight,
  Braces,
  Database,
  Layers3,
  Network,
  ShieldCheck,
  Sparkles,
  Terminal,
  Workflow,
} from "lucide-react";
import MagicBento, { MagicBentoCard } from "../react-bits/MagicBento";
import CountUp from "../react-bits/CountUp";
import { useReducedMotion } from "../../motion";
import type { ProgressRecord } from "../../progress";
import type { CurriculumData } from "../../types";
import { countMarks } from "./graph";

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
/** "r, g, b" so MagicBento can derive glow alphas. */
const domainColors = [
  "139, 120, 230",
  "81, 159, 212",
  "165, 120, 206",
  "59, 158, 148",
  "194, 135, 80",
  "115, 155, 82",
  "165, 108, 174",
  "206, 118, 142",
];

function Count({ value }: { value: number }) {
  const reduced = useReducedMotion();
  return (
    <strong>
      <span className="sr-only">{value}</span>
      <span aria-hidden="true">
        {reduced ? value : <CountUp to={value} duration={0.9} />}
      </span>
    </strong>
  );
}

export function DomainBento({
  curriculum,
  progress,
  onOpenDomain,
}: {
  curriculum: CurriculumData;
  progress: ProgressRecord;
  onOpenDomain: (categoryId: string) => void;
}) {
  const { t } = useTranslation("curriculum");
  return (
    <section
      className="curriculum-domains"
      aria-labelledby="curriculum-domains-title"
    >
      <div className="curriculum-section-heading">
        <h2 id="curriculum-domains-title">{t("domains.heading")}</h2>
        <span>{t("domains.hint")}</span>
      </div>
      <MagicBento
        className="curriculum-bento"
        glowColor={domainColors[0]}
        data-testid="curriculum-domains"
      >
        {curriculum.categories.map((category, index) => {
          const Icon = domainIcons[index % domainIcons.length];
          const color = domainColors[index % domainColors.length];
          const lessons = curriculum.lessons.filter(
            (lesson) => lesson.category_id === category.id,
          );
          const available = lessons.filter(
            (lesson) => lesson.status === "available",
          ).length;
          const planned = lessons.length - available;
          const marks = countMarks(progress, lessons);
          const hasProgress = marks.opened + marks.ran + marks.quizzed > 0;
          return (
            <MagicBentoCard
              key={category.id}
              glowColor={color}
              className="curriculum-domain-card"
              style={{ "--domain-color": `rgb(${color})` } as CSSProperties}
              data-testid="curriculum-domain-card"
              data-category={category.id}
              data-available={available}
              data-planned={planned}
            >
              <button
                type="button"
                className="curriculum-domain"
                aria-label={t("domains.open", { title: category.title })}
                onClick={() => onOpenDomain(category.id)}
              >
                <span className="curriculum-domain-top">
                  <Icon size={20} aria-hidden="true" />
                  <span aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                </span>
                <span className="curriculum-domain-title">{category.title}</span>
                <span className="curriculum-domain-description">
                  {category.description}
                </span>
                <span className="curriculum-domain-counts">
                  <span className={available ? "has-available" : ""}>
                    <Count value={available} />
                    {t("domains.available")}
                  </span>
                  <span>
                    <Count value={planned} />
                    {t("domains.planned")}
                  </span>
                  <span>{t("domains.modules", { n: category.modules.length })}</span>
                </span>
                <span
                  className="curriculum-domain-progress"
                  data-testid="curriculum-domain-progress"
                  data-opened={marks.opened}
                  data-ran={marks.ran}
                  data-quizzed={marks.quizzed}
                >
                  <span className="sr-only">{t("domains.progressLabel")}</span>
                  {hasProgress ? (
                    <>
                      <span>{t("domains.opened", { n: marks.opened })}</span>
                      <span>{t("domains.ran", { n: marks.ran })}</span>
                      <span>{t("domains.quizzed", { n: marks.quizzed })}</span>
                    </>
                  ) : (
                    <span>{t("domains.noProgress")}</span>
                  )}
                  <ArrowUpRight size={15} aria-hidden="true" />
                </span>
              </button>
            </MagicBentoCard>
          );
        })}
      </MagicBento>
    </section>
  );
}
