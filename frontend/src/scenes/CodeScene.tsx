import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../motion";
import { CodeLines } from "./code/CodeLines";
import { DesignDecisions } from "./code/DesignDecisions";
import { FileList } from "./code/FileList";
import { NotesColumn } from "./code/NotesColumn";
import { PromptSection, ToolsSection } from "./code/ReferenceSections";
import { WhatsNew } from "./code/WhatsNew";
import { splitLines } from "./code/model";
import { prismLanguage } from "./code/paths";
import { useCodeColumn } from "./code/useCodeColumn";
import { useEvidence } from "./code/useEvidence";
import { useLessonCode } from "./code/useLessonCode";
import { useNoteLayout } from "./code/useNoteLayout";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";
import "../styles/code-reading.css";

type Focus = { path: string; start: number; end: number; nonce: number };

/** 读码：what's new, file · code · notes, prompt and tools, then design decisions. */
export function CodeScene({ studio }: SceneProps) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  const reduced = useReducedMotion();
  const detail = studio.detail!;
  const lessonCode = useLessonCode(detail.id);
  const activeIndex = detail.sources[studio.source] ? studio.source : 0;
  const activeSource = detail.sources[activeIndex];
  const activePath = activeSource?.path ?? "";
  const { decisions, tools, notes, annotated, items } = useCodeColumn(
    detail,
    lessonCode.code,
    activePath,
  );
  const { evidence, openEvidence, clearEvidence } = useEvidence(studio);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [activeNote, setActiveNote] = useState<string | null>(null);
  const { frameRef, notesRef, itemRef, layout } = useNoteLayout(
    items,
    activeSource?.content,
  );

  // A different lesson or file starts without stale highlights.
  useEffect(() => {
    setFocus(null);
    setActiveNote(null);
    clearEvidence();
  }, [detail.id, clearEvidence]);

  // Scroll after the target file has rendered; reduced motion jumps instantly.
  useEffect(() => {
    if (!focus || focus.path !== activePath) return;
    frameRef.current
      ?.querySelector<HTMLElement>(`[data-line="${focus.start}"]`)
      ?.scrollIntoView({
        block: "center",
        behavior: reduced ? "auto" : "smooth",
      });
  }, [focus, activePath, reduced, frameRef]);

  const jump = (path: string, start: number, end = start) => {
    const index = detail.sources.findIndex((source) => source.path === path);
    if (index < 0) return;
    if (index !== activeIndex) studio.setSource(index);
    setFocus({ path, start, end, nonce: Date.now() });
  };

  const fileLines = activeSource ? splitLines(activeSource.content).length : 0;
  return (
    <div className="scene-code learning-experience" data-testid="scene-code">
      <section className="learn-tab-content code-intro">
        <h2>{t("title")}</h2>
        <p>{t("help")}</p>
      </section>
      {lessonCode.status === "ready" && (
        <WhatsNew code={lessonCode.code} onJump={jump} />
      )}
      {lessonCode.status === "loading" && (
        <p className="learn-empty" role="status">
          {t("loading")}
        </p>
      )}
      {lessonCode.status === "error" && (
        <p className="learn-empty" role="alert" data-testid="code-unavailable">
          {t("unavailable", { message: lessonCode.error })}
        </p>
      )}
      {activeSource ? (
        <div className="code-reader" data-testid="code-reader">
          <FileList
            sources={detail.sources}
            activeIndex={activeIndex}
            onSelect={studio.setSource}
          />
          <div className="code-stage">
            <div
              className="learn-code-frame code-frame"
              data-testid="learn-source-code"
              data-path={activePath}
              ref={frameRef}
              role="region"
              aria-label={t("codeRegion", { path: activePath })}
            >
              <div className="code-frame-head">
                <span>{activePath}</span>
                <span>{t("lineCount", { value: fileLines })}</span>
              </div>
              <CodeLines
                content={activeSource.content}
                language={prismLanguage(activeSource.language)}
                annotated={annotated}
                focus={focus && focus.path === activePath ? focus : null}
                active={
                  notes.find((note) => note.key === activeNote)?.line ?? null
                }
              />
            </div>
            <NotesColumn
              items={items}
              layout={layout}
              columnRef={notesRef}
              itemRef={itemRef}
              activeNote={activeNote}
              onNote={(key, line) => {
                setActiveNote(key);
                jump(activePath, line);
              }}
              evidence={evidence}
              onOpenEvidence={openEvidence}
            />
          </div>
        </div>
      ) : (
        <p className="learn-empty">{t("empty")}</p>
      )}
      <PromptSection prompt={detail.system_prompt} />
      <ToolsSection
        definitions={detail.tools}
        tools={tools}
        evidence={evidence}
        onOpenEvidence={openEvidence}
      />
      <DesignDecisions decisions={decisions} />
    </div>
  );
}
