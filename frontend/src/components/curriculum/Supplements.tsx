import { useTranslation } from "react-i18next";
import { ExternalLink } from "lucide-react";
import { httpUrl } from "../../lib/url";
import type { CurriculumData } from "../../types";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../ui/accordion";
import { TextList } from "./TextList";

/** Electives, curriculum principles and reference sources below the list. */
export function Supplements({ curriculum }: { curriculum: CurriculumData }) {
  const { t } = useTranslation("curriculum");
  return (
    <>
      {curriculum.electives.length > 0 && (
        <section className="panel curriculum-supplement">
          <h2>{t("supplements.electives")}</h2>
          <p>{t("supplements.electivesHelp")}</p>
          <Accordion type="multiple">
            {curriculum.electives.map((elective) => (
              <AccordionItem
                className="curriculum-elective"
                key={elective.id}
                value={elective.id}
              >
                <AccordionTrigger className="curriculum-elective-trigger">
                  {elective.title}
                </AccordionTrigger>
                <AccordionContent>
                  <p>{elective.description}</p>
                  <h4>{t("supplements.prerequisites")}</h4>
                  <p>
                    {elective.prerequisites
                      .map(
                        (id) =>
                          curriculum.lessons.find((lesson) => lesson.id === id)
                            ?.title || id,
                      )
                      .join(t("list.separator")) || t("supplements.none")}
                  </p>
                  <h4>{t("supplements.topics")}</h4>
                  <TextList items={elective.topics} />
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      )}
      <section className="panel curriculum-supplement curriculum-principles-panel">
        <h2>{t("supplements.principles")}</h2>
        <TextList items={curriculum.principles} />
      </section>
      <section className="panel curriculum-supplement curriculum-sources-panel">
        <h2>{t("supplements.sources")}</h2>
        <div className="curriculum-source-grid">
          {curriculum.sources.map((source) => {
            const url = httpUrl(source.url);
            return (
              <div className="curriculum-source" key={source.id}>
                <h3>
                  {url ? (
                    <a href={url} target="_blank" rel="noopener noreferrer">
                      {source.title}
                      <ExternalLink size={13} />
                    </a>
                  ) : (
                    source.title
                  )}
                </h3>
                <p>{source.role}</p>
                <p>{source.adaptation}</p>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}
