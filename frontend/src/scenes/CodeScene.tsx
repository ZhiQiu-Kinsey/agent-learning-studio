import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../motion";
import { CodeLines } from "./code/CodeLines";
import { DesignDecisions } from "./code/DesignDecisions";
import { FileList } from "./code/FileList";
import { NotesColumn } from "./code/NotesColumn";
import { PromptSection, ToolsSection } from "./code/ReferenceSections";
import { WhatsNew } from "./code/WhatsNew";
import { codeSegments, splitLines } from "./code/model";
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
  const { decisions, annotations, tools, notes, annotated, items } =
    useCodeColumn(detail, lessonCode.code, activePath);
  // 展开过的空段，键为“路径::空段键”；showAll 时整份文件显示。
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const [showAll, setShowAll] = useState(false);
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
    setExpanded(new Set());
    setShowAll(false);
    clearEvidence();
  }, [detail.id, clearEvidence]);

  // 打开一课时先显示有批注的文件，而不是清单里的第一个文件。
  useEffect(() => {
    const annotatedPaths = new Set(annotations.map((block) => block.path));
    if (!annotatedPaths.size || annotatedPaths.has(activePath)) return;
    const index = detail.sources.findIndex((source) =>
      annotatedPaths.has(source.path),
    );
    if (index >= 0) studio.setSource(index);
    // Only on lesson change: afterwards the learner chooses files freely.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  const fileText = useMemo(
    () => (activeSource ? splitLines(activeSource.content) : []),
    [activeSource],
  );
  const fileLines = fileText.length;
  const segmentsFor = useCallback(
    (path: string, lines: readonly string[]) => {
      const prefix = path + "::";
      const keys = new Set(
        [...expanded]
          .filter((key) => key.startsWith(prefix))
          .map((key) => key.slice(prefix.length)),
      );
      return codeSegments(lines, annotations, path, keys, showAll);
    },
    [annotations, expanded, showAll],
  );
  const segments = useMemo(
    () => segmentsFor(activePath, fileText),
    [segmentsFor, activePath, fileText],
  );
  const hasFocusView = annotations.some((block) => block.path === activePath);
  const expand = useCallback(
    (path: string, keys: string[]) =>
      setExpanded((previous) => {
        const next = new Set(previous);
        keys.forEach((key) => next.add(path + "::" + key));
        return next;
      }),
    [],
  );

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
    // 目标行若在收起的空段里，先把这些空段展开。
    const lines = splitLines(detail.sources[index].content);
    const hidden = segmentsFor(path, lines).flatMap((segment) =>
      segment.kind === "gap" && segment.start <= end && start <= segment.end
        ? [segment.key]
        : [],
    );
    if (hidden.length) expand(path, hidden);
    setFocus({ path, start, end, nonce: Date.now() });
  };
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
                <span>
                  {hasFocusView && (
                    <button
                      type="button"
                      className="code-view-toggle"
                      data-testid="code-show-all"
                      aria-pressed={showAll}
                      onClick={() => setShowAll((value) => !value)}
                    >
                      {showAll ? t("showFocused") : t("showAll")}
                    </button>
                  )}
                  {t("lineCount", { value: fileLines })}
                </span>
              </div>
              <CodeLines
                content={activeSource.content}
                language={prismLanguage(activeSource.language)}
                segments={segments}
                onExpand={(key) => expand(activePath, [key])}
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
