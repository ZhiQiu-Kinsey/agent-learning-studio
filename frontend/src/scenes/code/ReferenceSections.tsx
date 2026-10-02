import { useTranslation } from "react-i18next";
import { Code } from "../../components/Code";
import type { Detail } from "../../types";
import { EvidenceButton } from "./EvidenceButton";
import type { Evidence } from "./useEvidence";

/** The system prompt the model receives, as prose. */
export function PromptSection({
  prompt,
}: {
  prompt: string | null | undefined;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  return (
    <section className="learn-reference-section" data-testid="code-prompt">
      <span className="reading-eyebrow">{t("promptEyebrow")}</span>
      <h2>{t("promptTitle")}</h2>
      <p>{t("promptHelp")}</p>
      {prompt ? (
        <div className="learn-code-frame code-prompt-frame">
          <Code content={prompt} language="text" />
        </div>
      ) : (
        <p>{t("noPrompt")}</p>
      )}
    </section>
  );
}

/** The tool definitions sent with each request, with evidence buttons per tool. */
export function ToolsSection({
  definitions,
  tools,
  evidence,
  onOpenEvidence,
}: {
  definitions: Detail["tools"];
  tools: string[];
  evidence: Evidence | null;
  onOpenEvidence: (name: string, at: string) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  return (
    <section className="learn-reference-section" data-testid="code-tools">
      <span className="reading-eyebrow">{t("toolsEyebrow")}</span>
      <h2>{t("toolsTitle")}</h2>
      <p>{t("toolsHelp")}</p>
      {tools.length > 0 && (
        <div className="code-tool-evidence">
          {tools.map((name) => (
            <EvidenceButton
              key={name}
              name={name}
              at={`tools:${name}`}
              evidence={evidence}
              onOpen={onOpenEvidence}
            />
          ))}
        </div>
      )}
      <div className="learn-code-frame">
        <Code
          content={JSON.stringify(definitions, null, 2) ?? t("noTools")}
          language="json"
        />
      </div>
    </section>
  );
}
