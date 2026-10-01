import Markdown from "react-markdown";
import { useTranslation } from "react-i18next";
import { AlertTriangle, ExternalLink, Info, ShieldAlert } from "lucide-react";
import type { BlockOf } from "../view";

/** Generic renderers shared by lesson scenes and onboarding chapters. */

export function StepsBlock({ block }: { block: BlockOf<"steps"> }) {
  return (
    <section className="content-block content-steps" data-testid="block-steps">
      {block.title && <h3>{block.title}</h3>}
      {block.paragraphs.map((paragraph, index) => (
        <div className="reading-prose" key={index}>
          <Markdown>{paragraph}</Markdown>
        </div>
      ))}
      <ol>
        {block.items.map((item) => (
          <li key={item.id}>
            <Markdown>{item.text}</Markdown>
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
          <Markdown>{paragraph}</Markdown>
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
                    <Markdown>{cell}</Markdown>
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
            <Markdown>{paragraph}</Markdown>
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
        <span>{block.claim}</span>
      </p>
      <p>
        <strong>{t("correction")}</strong>
        <span>{block.correction}</span>
      </p>
    </section>
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
