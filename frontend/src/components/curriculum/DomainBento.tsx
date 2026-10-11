import { useRef, type CSSProperties } from "react";
import { useInView } from "motion/react";
import { useTranslation } from "react-i18next";
import {
  ArrowUpRight,
  Braces,
  BrainCircuit,
  Database,
  Layers3,
  Network,
  ShieldCheck,
  Sparkles,
  SquareTerminal,
  Terminal,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import MagicBento, { MagicBentoCard } from "../react-bits/MagicBento";
import CountUp from "../react-bits/CountUp";
import { Backdrop } from "../backdrops/Backdrop";
import { useMotion, useReducedMotion } from "../../motion";
import type { ProgressRecord } from "../../progress";
import type { CurriculumData } from "../../types";

type CurriculumCategory = CurriculumData["categories"][number];
import { countMarks } from "./graph";
import { domainAtmosphere } from "./atmosphere";
import { useResolvedTheme } from "../../hooks/useTheme";

const domainIcons: Record<string, LucideIcon> = {
  A: Terminal,
  B: Braces,
  C: Layers3,
  R: BrainCircuit,
  D: Database,
  E: Workflow,
  K: SquareTerminal,
  F: ShieldCheck,
  G: Network,
  H: Sparkles,
};
const fallbackIcons = [Terminal, Braces, Layers3, Database, Workflow, Network];

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

/**
 * The tile's atmosphere window. At full motion with WebGL every tile keeps its
 * own live backdrop mounted (no hover needed, no on-screen cap: maintainer
 * decision 2026-10-06); Backdrop still unmounts the shader off screen. Static
 * motion or missing WebGL shows the preset's gradient with faint contours.
 */
function DomainWindow({
  category,
  index,
  live,
  Icon,
}: {
  category: CurriculumCategory;
  index: number;
  live: boolean;
  Icon: LucideIcon;
}) {
  const theme = useResolvedTheme();
  const atmosphere = domainAtmosphere(category.id, theme);
  return (
    <span
      className="curriculum-domain-window"
      aria-hidden="true"
      data-testid="curriculum-domain-window"
      data-atmosphere={live ? "live" : "still"}
    >
      {live ? (
        <Backdrop
          name={atmosphere.backdrop}
          className="curriculum-domain-live"
        />
      ) : (
        <span
          className="curriculum-domain-still"
          style={{ background: atmosphere.fallback }}
        />
      )}
      <span className="curriculum-domain-window-scrim" />
      <span className="curriculum-domain-glyph">
        <Icon size={22} strokeWidth={1.6} />
      </span>
      <span className="curriculum-domain-index">
        {String(index + 1).padStart(2, "0")}
        <i>{category.id}</i>
      </span>
    </span>
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
  const { reduced, webgl } = useMotion();
  const theme = useResolvedTheme();
  const sectionRef = useRef<HTMLElement>(null);
  const entered = useInView(sectionRef, { once: true, amount: 0.08 });
  const live = !reduced && webgl;

  return (
    <section
      ref={sectionRef}
      className="curriculum-domains"
      aria-labelledby="curriculum-domains-title"
      data-entered={entered || reduced}
    >
      <div className="curriculum-section-heading">
        <h2 id="curriculum-domains-title">{t("domains.heading")}</h2>
        <span>{t("domains.hint")}</span>
      </div>
      <MagicBento
        className="curriculum-bento"
        glowColor={theme === "dark" ? "109, 93, 252" : "93, 76, 235"}
        data-testid="curriculum-domains"
      >
        {curriculum.categories.map((category, index) => {
          const Icon =
            domainIcons[category.id] ??
            fallbackIcons[index % fallbackIcons.length];
          const { accent } = domainAtmosphere(category.id, theme);
          const lessons = curriculum.lessons.filter(
            (lesson) => lesson.category_id === category.id,
          );
          const available = lessons.filter(
            (lesson) => lesson.status === "available",
          ).length;
          const planned = lessons.length - available;
          const marks = countMarks(progress, lessons);
          const hasProgress = marks.opened + marks.ran + marks.quizzed > 0;
          const ratio = lessons.length ? available / lessons.length : 0;
          return (
            <MagicBentoCard
              key={category.id}
              glowColor={accent}
              particleCount={14}
              className="curriculum-domain-card"
              style={
                {
                  "--domain-color": `rgb(${accent})`,
                  "--domain-rgb": accent,
                  "--domain-ratio": ratio,
                  "--i": index,
                } as CSSProperties
              }
              data-testid="curriculum-domain-card"
              data-category={category.id}
              data-available={available}
              data-planned={planned}
            >
              <div className="curriculum-domain-shell">
                <DomainWindow
                  category={category}
                  index={index}
                  live={live}
                  Icon={Icon}
                />
                <button
                  type="button"
                  className="curriculum-domain"
                  aria-label={t("domains.open", { title: category.title })}
                  onClick={() => onOpenDomain(category.id)}
                >
                  <span className="curriculum-domain-title">
                    {category.title}
                  </span>
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
                    <span>
                      {t("domains.modules", { count: category.modules.length })}
                    </span>
                  </span>
                  <span className="curriculum-domain-meter" aria-hidden="true">
                    <i />
                  </span>
                  <span
                    className="curriculum-domain-progress"
                    data-testid="curriculum-domain-progress"
                    data-opened={marks.opened}
                    data-ran={marks.ran}
                    data-quizzed={marks.quizzed}
                  >
                    <span className="sr-only">
                      {t("domains.progressLabel")}
                    </span>
                    {hasProgress ? (
                      <>
                        <span>{t("domains.opened", { count: marks.opened })}</span>
                        <span>{t("domains.ran", { count: marks.ran })}</span>
                        <span>
                          {t("domains.quizzed", { count: marks.quizzed })}
                        </span>
                      </>
                    ) : (
                      <span>{t("domains.noProgress")}</span>
                    )}
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </span>
                </button>
              </div>
            </MagicBentoCard>
          );
        })}
      </MagicBento>
    </section>
  );
}
