import Markdown from "react-markdown";

export function Answer({ content }: { content: string }) {
  return (
    <div className="answer-content" data-testid="lab-answer">
      {/* Raw HTML stays text; Markdown's default URL filter blocks unsafe links. */}
      <Markdown>{content}</Markdown>
    </div>
  );
}
