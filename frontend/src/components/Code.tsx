import type { ReactNode, Ref } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-json";

function tokens(
  value: string | Prism.Token | (string | Prism.Token)[],
): ReactNode {
  if (typeof value === "string") return value;
  if (Array.isArray(value))
    return value.map((item, i) => <span key={i}>{tokens(item)}</span>);
  return <span className={`token ${value.type}`}>{tokens(value.content)}</span>;
}

/**
 * Render token text through React; code and model output never become executable HTML.
 * `mark` frames whole lines (0-based, inclusive) in a block `<mark>` so a guide or a
 * "locate" action can point at one field; the text itself is unchanged.
 */
export function Code({
  content,
  language = "json",
  mark,
  markRef,
}: {
  content: string;
  language?: string;
  mark?: { from: number; to: number } | null;
  markRef?: Ref<HTMLElement>;
}) {
  const grammar = Prism.languages[language] || Prism.languages.plain;
  const render = (text: string) =>
    grammar ? tokens(Prism.tokenize(text, grammar)) : text;
  if (!mark) {
    return (
      <pre className="code" tabIndex={0}>
        <code>{render(content)}</code>
      </pre>
    );
  }
  const lines = content.split("\n");
  const before = lines.slice(0, mark.from).join("\n");
  const after = lines.slice(mark.to + 1).join("\n");
  // The line break after the marked lines lives inside the block <mark>, so no
  // empty line appears between it and the text that follows.
  const marked =
    lines.slice(mark.from, mark.to + 1).join("\n") + (after ? "\n" : "");
  return (
    <pre className="code" tabIndex={0}>
      <code>
        {mark.from > 0 && render(`${before}\n`)}
        <mark className="code-mark" ref={markRef} data-evidence-mark="">
          {render(marked)}
        </mark>
        {after && render(after)}
      </code>
    </pre>
  );
}
