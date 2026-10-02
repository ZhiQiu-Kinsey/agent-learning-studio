import { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-json";
import {
  splitLines,
  tokenLines,
  type CodeSegment,
  type TokenLike,
} from "./model";

/**
 * Source with line numbers; every visible line is a block so notes can align
 * to it. Collapsed gaps (lines outside the annotated range, folded platform
 * code) render as one button that expands them in place.
 */
export const CodeLines = memo(function CodeLines({
  content,
  language,
  segments,
  annotated,
  focus,
  active,
  onExpand,
}: {
  content: string;
  language: string;
  segments: readonly CodeSegment[];
  annotated: Set<number>;
  focus: { start: number; end: number } | null;
  active: number | null;
  onExpand: (key: string) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  const lines = useMemo(() => {
    const grammar = Prism.languages[language];
    return grammar
      ? tokenLines(Prism.tokenize(content, grammar) as unknown as TokenLike[])
      : splitLines(content).map((text) => (text ? [{ text, types: [] }] : []));
  }, [content, language]);
  const row = (line: number) => {
    const segments = lines[line - 1] ?? [];
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
  };
  return (
    <pre className="code code-lines">
      <code>
        {segments.map((segment) => {
          if (segment.kind === "lines") {
            const rows = [];
            for (let line = segment.start; line <= segment.end; line++)
              rows.push(row(line));
            return rows;
          }
          const count = segment.end - segment.start + 1;
          return (
            <button
              key={segment.key}
              type="button"
              className="code-gap"
              data-testid="code-gap"
              data-reason={segment.reason}
              data-start={segment.start}
              data-end={segment.end}
              onClick={() => onExpand(segment.key)}
            >
              {segment.reason === "fold"
                ? t("gap.fold", { label: segment.label, count })
                : t("gap.outside", {
                    start: segment.start,
                    end: segment.end,
                    count,
                  })}
              {"\n"}
            </button>
          );
        })}
      </code>
    </pre>
  );
});
