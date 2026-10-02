import { useTranslation } from "react-i18next";
import { Terminal } from "lucide-react";
import type { StudioState } from "../../../hooks/useStudio";
import GlideSelect from "../../react-bits/GlideSelect";
import { pickerColors } from "../../lab/controlColors";
import { Code } from "../../Code";

/** The lesson's real Python source, one file at a time, read-only. */
export function SourcePane({ studio: s }: { studio: StudioState }) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.source" });
  const file = s.detail?.sources[s.source];
  return (
    <>
      <div className="source-toolbar">
        <Terminal size={16} />
        <GlideSelect
          {...pickerColors}
          ariaLabel={t("file")}
          className="full-picker"
          value={String(s.source)}
          onChange={(v) => s.setSource(Number(v))}
          options={
            s.detail?.sources.map((f, i) => ({
              value: String(i),
              label: f.path,
            })) || []
          }
        />
        <small>{t("readonly")}</small>
      </div>
      {file && (
        <Code
          content={file.content}
          language={file.language === "py" ? "python" : file.language}
        />
      )}
    </>
  );
}

/** The system prompt and tool definitions the lesson sends to the model. */
export function PromptPane({ detail }: { detail: StudioState["detail"] }) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.prompt" });
  return (
    <>
      <h3>{t("system")}</h3>
      <pre>{detail?.system_prompt}</pre>
      <h3>{t("tools")}</h3>
      <Code content={JSON.stringify(detail?.tools, null, 2) || "[]"} />
    </>
  );
}
