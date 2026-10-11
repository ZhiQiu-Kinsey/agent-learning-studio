import Markdown from "react-markdown";

/** `lang` is the run's language, so a Chinese answer in the English UI is marked as Chinese. */
export function Answer({ content, lang }: { content: string; lang?: string }) {
  return (
    <div className="answer-content" data-testid="lab-answer" lang={lang}>
      {/* Raw HTML stays text; Markdown's default URL filter blocks unsafe links. */}
      <Markdown>{content}</Markdown>
    </div>
  );
}
