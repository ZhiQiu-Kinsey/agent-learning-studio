import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import ScrollVelocity from "../react-bits/ScrollVelocity";
import type { CurriculumData } from "../../types";
import { categoryTint } from "./tint";

/**
 * Module titles straight from the catalogue, drifting in two rows. The rows are
 * decorative copies; the list below them is what assistive tech reads.
 */
export function HomeTopics({ curriculum }: { curriculum: CurriculumData }) {
  const { t } = useTranslation("home");
  const modules = curriculum.categories.flatMap((category) =>
    category.modules.map((module) => ({
      id: module.id,
      title: module.title,
      color: categoryTint(category.id).color,
    })),
  );
  const half = Math.ceil(modules.length / 2);
  const row = (items: typeof modules) => (
    <>
      {items.map((item) => (
        <Fragment key={item.id}>
          <span className="home-topic" style={{ color: item.color }}>
            {item.title}
          </span>
          <span className="home-topic-star">✦</span>
        </Fragment>
      ))}
    </>
  );
  return (
    <section
      className="home-section home-topics"
      aria-labelledby="home-topics-title"
    >
      <header className="home-section-head">
        <p className="home-eyebrow">{t("topics.kicker")}</p>
        <h2 id="home-topics-title">{t("topics.title")}</h2>
        <p>
          {t("topics.lead", {
            categories: curriculum.categories.length,
            modules: modules.length,
          })}
        </p>
      </header>
      <div className="home-topics-band">
        <ScrollVelocity
          rows={[row(modules.slice(0, half)), row(modules.slice(half))]}
          velocity={36}
          copies={3}
          className="home-topics-row"
        />
      </div>
      <ul className="sr-only" aria-label={t("topics.listLabel")}>
        {modules.map((item) => (
          <li key={item.id}>{item.title}</li>
        ))}
      </ul>
    </section>
  );
}
