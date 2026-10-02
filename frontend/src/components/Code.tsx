import type { ReactNode } from "react";
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

/** Render token text through React; code and model output never become executable HTML. */
export function Code({
  content,
  language = "json",
}: {
  content: string;
  language?: string;
}) {
  const grammar = Prism.languages[language] || Prism.languages.plain;
  return (
    <pre className="code" tabIndex={0}>
      <code>
        {grammar ? tokens(Prism.tokenize(content, grammar)) : content}
      </code>
    </pre>
  );
}
