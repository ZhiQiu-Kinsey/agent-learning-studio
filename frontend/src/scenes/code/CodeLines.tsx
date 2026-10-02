import { memo, useMemo } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-json";
import { splitLines, tokenLines, type TokenLike } from "./model";

/** Source with line numbers; every line is a block so notes can align to it. */
export const CodeLines = memo(function CodeLines({
  content,
  language,
  annotated,
  focus,
  active,
}: {
  content: string;
  language: string;
  annotated: Set<number>;
  focus: { start: number; end: number } | null;
  active: number | null;
}) {
  const lines = useMemo(() => {
    const grammar = Prism.languages[language];
    return grammar
      ? tokenLines(Prism.tokenize(content, grammar) as unknown as TokenLike[])
      : splitLines(content).map((text) => (text ? [{ text, types: [] }] : []));
  }, [content, language]);
  return (
    <pre className="code code-lines">
      <code>
        {lines.map((segments, index) => {
          const line = index + 1;
          return (
            <span
              key={line}
              className="code-line"
              data-line={line}
              data-annotated={annotated.has(line) || undefined}
              data-focused={
                (focus && line >= focus.start && line <= focus.end) || undefined
              }
              data-active={active === line || undefined}
            >
              {segments.map((segment, i) =>
                segment.types.length ? (
                  <span key={i} className={`token ${segment.types.join(" ")}`}>
                    {segment.text}
                  </span>
                ) : (
                  segment.text
                ),
              )}
              {"\n"}
            </span>
          );
        })}
      </code>
    </pre>
  );
});
