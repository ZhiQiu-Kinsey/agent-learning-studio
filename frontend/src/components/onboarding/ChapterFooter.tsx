import { useTranslation } from "react-i18next";
import { ArrowLeft, ArrowRight, ExternalLink } from "lucide-react";
import type { Chapter } from "../../content/types.gen";
import { Button } from "../ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../ui/accordion";
import type { ChapterContent } from "./chapters";

/** Collapsible reading sources of a chapter. */
function ChapterSources({
  references,
}: {
  references: ChapterContent["references"];
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  return (
    <Accordion
      type="single"
      collapsible
      className="onboarding-sources"
      data-testid="onboarding-sources"
    >
      <AccordionItem value="sources">
        <AccordionTrigger>
          {t("sources", { count: references.length })}
        </AccordionTrigger>
        <AccordionContent>
          <ul>
            {references.map((reference) => (
              <li key={reference.url}>
                <a href={reference.url} target="_blank" rel="noreferrer">
                  {reference.title}
                  <ExternalLink size={12} />
                </a>
              </li>
            ))}
          </ul>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

/** Sources, then previous / next chapter (the last one leads to the first lesson). */
export function ChapterFooter({
  chapter,
  chapters,
  index,
  onNavigate,
  onStart,
}: {
  chapter: ChapterContent;
  chapters: Chapter[];
  index: number;
  onNavigate: (index: number) => void;
  onStart: () => void;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  const next = chapters[index + 1];
  return (
    <>
      <ChapterSources references={chapter.references} />
      <div className="onboarding-next">
        <Button
          variant="ghost"
          disabled={index === 0}
          onClick={() => onNavigate(index - 1)}
        >
          <ArrowLeft size={15} />
          {t("previous")}
        </Button>
        <Button
          data-testid="onboarding-next"
          className="onboarding-next-button"
          onClick={() => (next ? onNavigate(index + 1) : onStart())}
        >
          {next ? t("next", { title: next.title }) : t("startLesson")}
          <ArrowRight size={15} />
        </Button>
      </div>
    </>
  );
}
