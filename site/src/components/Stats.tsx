import { useTranslation } from "react-i18next";
import CountUp from "@studio/components/react-bits/CountUp";
import curriculum from "../generated/curriculum.json";

/** Counts taken from the generated catalog; only the two fixed numbers are written here. */
export function Stats() {
  const { t } = useTranslation("site", { keyPrefix: "stats" });
  const stats = [
    { id: "lessons", value: curriculum.lessonCount },
    { id: "domains", value: curriculum.categories.length },
    { id: "steps", value: 5 },
    { id: "languages", value: 2 },
  ] as const;
  return (
    <dl className="site-stats">
      {stats.map((stat) => (
        <div key={stat.id} data-testid={`stat-${stat.id}`}>
          <dt>
            <span className="sr-only">{stat.value}</span>
            <span aria-hidden="true">
              <CountUp to={stat.value} duration={1.4} className="site-stat-value" />
            </span>
          </dt>
          <dd>{t(stat.id)}</dd>
        </div>
      ))}
    </dl>
  );
}
