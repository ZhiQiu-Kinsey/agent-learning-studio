import { useTranslation } from "react-i18next";
import { AlertTriangle, ExternalLink, Info, ShieldAlert } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";
import type { BlockOf } from "../view";
import { GlossaryMarkdown, GlossaryText } from "../glossary/Glossary";

/** Generic renderers shared by lesson scenes and onboarding chapters. */

export function StepsBlock({ block }: { block: BlockOf<"steps"> }) {
  return (
    <section className="content-block content-steps" data-testid="block-steps">
      {block.title && <h3>{block.title}</h3>}
      {block.paragraphs.map((paragraph, index) => (
        <div className="reading-prose" key={index}>
          <GlossaryMarkdown>{paragraph}</GlossaryMarkdown>
        </div>
      ))}
      <ol>
        {block.items.map((item) => (
          <li key={item.id}>
            <GlossaryMarkdown>{item.text}</GlossaryMarkdown>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function CompareBlock({ block }: { block: BlockOf<"compare"> }) {
  return (
    <section
      className="content-block content-compare"
      data-testid="block-compare"
    >
      {block.title && <h3>{block.title}</h3>}
      {block.paragraphs.map((paragraph, index) => (
        <div className="reading-prose" key={index}>
          <GlossaryMarkdown>{paragraph}</GlossaryMarkdown>
        </div>
      ))}
      <div className="content-table">
        <table>
          <thead>
            <tr>
              {block.columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, index) => (
              <tr key={index}>
                {row.map((cell, column) => (
                  <td key={column}>
                    <GlossaryMarkdown>{cell}</GlossaryMarkdown>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const calloutIcons = {
  note: Info,
  warning: AlertTriangle,
  boundary: ShieldAlert,
};

export function CalloutBlock({ block }: { block: BlockOf<"callout"> }) {
  const Icon = calloutIcons[block.tone];
  return (
    <aside
      className="content-block content-callout"
      data-tone={block.tone}
      data-testid="block-callout"
    >
      <Icon size={18} aria-hidden="true" />
      <div>
        {block.title && <h3>{block.title}</h3>}
        {block.paragraphs.map((paragraph, index) => (
          <div className="reading-prose" key={index}>
            <GlossaryMarkdown>{paragraph}</GlossaryMarkdown>
          </div>
        ))}
      </div>
    </aside>
  );
}

export function MisconceptionBlock({
  block,
}: {
  block: BlockOf<"misconception">;
}) {
  const { t } = useTranslation("blocks", { keyPrefix: "misconception" });
  return (
    <section
      className="content-block content-misconception"
      data-testid="block-misconception"
    >
      <p>
        <strong>{t("claim")}</strong>
        <span>
          <GlossaryText text={block.claim} />
        </span>
      </p>
      <p>
        <strong>{t("correction")}</strong>
        <span>
          <GlossaryText text={block.correction} />
        </span>
      </p>
    </section>
  );
}

/**
 * Material beyond the main line (background, mechanism, a worked example),
 * folded by default. The summary sits beside the trigger rather than inside
 * it: glossary terms are focusable and must not nest in a button.
 */
export function DeepDiveBlock({ block }: { block: BlockOf<"deep-dive"> }) {
  const { t } = useTranslation("blocks", { keyPrefix: "deepDive" });
  return (
    <Accordion
      type="single"
      collapsible
      className="content-block content-deep-dive"
      data-testid="block-deep-dive"
    >
      <AccordionItem value={block.id}>
        <AccordionTrigger className="deep-dive-trigger hover:no-underline">
          <span className="deep-dive-heading">
            <span className="deep-dive-label">{t("label")}</span>
            <strong>{block.title}</strong>
          </span>
        </AccordionTrigger>
        {block.summary && (
          <p className="deep-dive-summary">
            <GlossaryText text={block.summary} />
          </p>
        )}
        <AccordionContent className="deep-dive-body">
          {block.paragraphs.map((paragraph, index) => (
            <div className="reading-prose" key={index}>
              <GlossaryMarkdown>{paragraph}</GlossaryMarkdown>
            </div>
          ))}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export function ReferencesBlock({ block }: { block: BlockOf<"references"> }) {
  const { t } = useTranslation("blocks", { keyPrefix: "references" });
  return (
    <section
      className="content-block content-references"
      data-testid="block-references"
    >
      <h3>{t("title")}</h3>
      <ul>
        {block.items.map((item) => (
          <li key={item.id}>
            <a href={item.url} target="_blank" rel="noreferrer">
              {item.title}
              <ExternalLink size={12} aria-hidden="true" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
