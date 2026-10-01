import { useTranslation } from "react-i18next";
import { Code } from "../components/Code";
import GlideSelect from "../components/react-bits/GlideSelect";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";

/** 读码：the lesson's real source files, system prompt and tool definitions. */
export function CodeScene({ studio }: SceneProps) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  const detail = studio.detail!;
  const activeSource = detail.sources[studio.source] ?? detail.sources[0];
  return (
    <div className="scene-code learning-experience" data-testid="scene-code">
      <section className="learn-tab-content">
        <div className="learn-source-toolbar">
          <div>
            <h2>{t("title")}</h2>
            <p>{t("help")}</p>
          </div>
          <GlideSelect
            className="learn-source-select"
            ariaLabel={t("select")}
            value={String(detail.sources.indexOf(activeSource))}
            options={detail.sources.map((file, index) => ({
              value: String(index),
              label: file.path,
              tag: file.language,
            }))}
            onChange={(value) => studio.setSource(Number(value))}
            disabled={!detail.sources.length}
            menuWidth={320}
            surfaceColor="var(--surface)"
            highlightColor="var(--surface-muted)"
            textColor="var(--text)"
            accentColor="var(--accent)"
          />
        </div>
        {activeSource ? (
          <div className="learn-code-frame" data-testid="learn-source-code">
            <Code
              content={activeSource.content}
              language={
                activeSource.language === "py"
                  ? "python"
                  : activeSource.language
              }
            />
          </div>
        ) : (
          <p className="learn-empty">{t("empty")}</p>
        )}
      </section>
      <section className="learn-reference-section" data-testid="code-prompt">
        <span className="reading-eyebrow">{t("promptEyebrow")}</span>
        <h2>{t("promptTitle")}</h2>
        <p>{t("promptHelp")}</p>
        {detail.system_prompt ? (
          <div className="learn-code-frame">
            <Code content={detail.system_prompt} language="text" />
          </div>
        ) : (
          <p>{t("noPrompt")}</p>
        )}
      </section>
      <section className="learn-reference-section" data-testid="code-tools">
        <span className="reading-eyebrow">{t("toolsEyebrow")}</span>
        <h2>{t("toolsTitle")}</h2>
        <p>{t("toolsHelp")}</p>
        <div className="learn-code-frame">
          <Code
            content={JSON.stringify(detail.tools, null, 2) ?? t("noTools")}
            language="json"
          />
        </div>
      </section>
    </div>
  );
}
