import { IllustrationFlow } from "../../content/blocks/IllustrationFlow";
import { GlossaryMarkdown } from "../../content/glossary/Glossary";
import { numeral, type ChapterContent } from "./chapters";
import { Reveal } from "./Reveal";

type Section = ChapterContent["sections"][number];

function SectionTable({ table }: { table: NonNullable<Section["table"]> }) {
  return (
    <div className="onboarding-table">
      <table>
        <thead>
          <tr>
            {table.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>
                  <GlossaryMarkdown>{cell}</GlossaryMarkdown>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One reading section, followed by the illustrations authored after it. */
export function ChapterSection({
  chapter,
  section,
  index,
}: {
  chapter: ChapterContent;
  section: Section;
  index: number;
}) {
  return (
    <>
      <Reveal
        as="section"
        className={`onboarding-section onboarding-section-${section.kind}`}
        data-testid="onboarding-section"
      >
        <h3>
          <span>{numeral(index)}</span>
          {section.title}
        </h3>
        {section.paragraphs.map((paragraph, i) => (
          <Reveal
            className="onboarding-prose"
            key={i}
            delay={Math.min(i, 3) * 0.06}
          >
            <GlossaryMarkdown>{paragraph}</GlossaryMarkdown>
          </Reveal>
        ))}
        {!!section.bullets?.length && (
          <ul>
            {section.bullets.map((bullet, i) => (
              <li key={i}>
                <GlossaryMarkdown>{bullet}</GlossaryMarkdown>
              </li>
            ))}
          </ul>
        )}
        {section.table && <SectionTable table={section.table} />}
      </Reveal>
      {chapter.flows
        .filter((flow) => flow.after === section.id)
        .map(({ block }) =>
          chapter.illustrations[block.illustration] ? (
            <Reveal key={block.id} className="onboarding-flow">
              <IllustrationFlow
                block={block}
                illustration={chapter.illustrations[block.illustration]}
              />
            </Reveal>
          ) : null,
        )}
    </>
  );
}
