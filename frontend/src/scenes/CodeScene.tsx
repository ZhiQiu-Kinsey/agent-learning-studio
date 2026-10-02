import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { useTranslation } from "react-i18next";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-json";
import { FlaskConical } from "lucide-react";
import { Code } from "../components/Code";
import FadeContent from "../components/react-bits/FadeContent";
import GlareHover from "../components/react-bits/GlareSheen";
import { blocksOfType, sceneBlocks } from "../content/view";
import { useReducedMotion } from "../motion";
import { requestScene } from "./LessonScenes";
import {
  annotatedLines,
  latestToolResult,
  notesForFile,
  splitLines,
  stackNotes,
  tokenLines,
  toolNames,
  whatsNewItems,
  type Annotation,
  type LessonCode,
  type PlacedNote,
  type TokenLike,
} from "./code/model";
import { useLessonCode } from "./code/useLessonCode";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";
import "../styles/code-reading.css";

const prismLanguage = (language: string) =>
  language === "py" ? "python" : language;
const basename = (path: string) => path.slice(path.lastIndexOf("/") + 1);
const dirname = (path: string) => path.slice(0, path.lastIndexOf("/") + 1);

type Focus = { path: string; start: number; end: number; nonce: number };
type Evidence = { name: string; at: string; reason: "noRun" | "notCalled" };
type ColumnItem =
  | { key: string; line: number; kind: "note"; note: PlacedNote }
  | { key: string; line: number; kind: "tool"; name: string };

/** Source with line numbers; every line is a block so notes can align to it. */
const CodeLines = memo(function CodeLines({
  content,
  language,
  annotated,
  focus,
  active,
}: {
  content: string;
  language: string;
  annotated: Set<number>;
  focus: { start: number; end: number } | null;
  active: number | null;
}) {
  const lines = useMemo(() => {
    const grammar = Prism.languages[language];
    return grammar
      ? tokenLines(Prism.tokenize(content, grammar) as unknown as TokenLike[])
      : splitLines(content).map((text) => (text ? [{ text, types: [] }] : []));
  }, [content, language]);
  return (
    <pre className="code code-lines">
      <code>
        {lines.map((segments, index) => {
          const line = index + 1;
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
        })}
      </code>
    </pre>
  );
});

function EvidenceButton({
  name,
  at,
  evidence,
  onOpen,
}: {
  name: string;
  at: string;
  evidence: Evidence | null;
  onOpen: (name: string, at: string) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code.evidence" });
  const shown = evidence?.at === at ? evidence : null;
  return (
    <div className="code-evidence">
      <button
        type="button"
        data-testid="code-evidence"
        data-tool={name}
        aria-label={t("label", { name })}
        onClick={() => onOpen(name, at)}
      >
        <FlaskConical size={14} aria-hidden="true" />
        <code>{name}</code>
        <span>{t("open")}</span>
      </button>
      {shown && (
        <p role="status" data-testid="code-evidence-status">
          {t(shown.reason, { name })}
        </p>
      )}
    </div>
  );
}

function WhatsNew({
  code,
  onJump,
}: {
  code: LessonCode;
  onJump: (path: string, start: number, end: number) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code.whatsNew" });
  const items = whatsNewItems(code);
  const compare = code.whats_new.compare_with;
  const unchanged = code.whats_new.unchanged.length;
  return (
    <section
      className="code-whats-new"
      data-testid="code-whats-new"
      aria-labelledby="code-whats-new-title"
    >
      <span className="reading-eyebrow">{t("eyebrow")}</span>
      <h2 id="code-whats-new-title">{t("title")}</h2>
      <p>
        {compare
          ? t("compared", { number: compare.number, title: compare.title })
          : t("first")}
      </p>
      {items.length ? (
        <ul>
          {items.map((item, index) => (
            <li
              key={`${item.path}:${item.name}:${item.start}`}
              style={{ "--i": index } as CSSProperties}
            >
              <button
                type="button"
                data-testid="code-whats-new-item"
                data-symbol={item.name}
                data-status={item.status}
                data-path={item.path}
                data-line={item.start}
                title={item.path}
                onClick={() => onJump(item.path, item.start, item.end)}
              >
                <span className="code-symbol-status">
                  {t(`status.${item.status}`)}
                </span>
                <span className="code-symbol-name">{item.name}</span>
                <span className="code-symbol-meta">
                  {t(`kind.${item.kind}`)} ·{" "}
                  {t("location", {
                    file: basename(item.path),
                    line: item.start,
                  })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p>{t("none")}</p>
      )}
      {compare && unchanged > 0 && (
        <p className="code-whats-new-unchanged">
          {t("unchanged", { value: unchanged })}
        </p>
      )}
    </section>
  );
}

/** 读码：what's new, file · code · notes, prompt and tools, then design decisions. */
export function CodeScene({ studio }: SceneProps) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  const reduced = useReducedMotion();
  const detail = studio.detail!;
  const lessonCode = useLessonCode(detail.id);
  const code = lessonCode.code;
  const activeIndex = detail.sources[studio.source] ? studio.source : 0;
  const activeSource = detail.sources[activeIndex];
  const activePath = activeSource?.path ?? "";
  const codeBlocks = sceneBlocks(detail.learning, "code");
  const decisions = blocksOfType(codeBlocks, "decision");
  const annotations: Annotation[] = useMemo(
    () =>
      code?.annotations ??
      blocksOfType(codeBlocks, "annotated-source").map((block) => ({
        id: block.id,
        path: block.path,
        start: block.start ?? null,
        end: block.end ?? null,
        notes: block.notes,
      })),
    // codeBlocks is derived from detail.learning, which changes with the lesson.
    [code, detail.learning],
  );
  const tools = useMemo(() => toolNames(detail.tools), [detail.tools]);
  const notes = useMemo(
    () => notesForFile(annotations, activePath),
    [annotations, activePath],
  );
  const annotated = useMemo(() => annotatedLines(notes), [notes]);
  const items: ColumnItem[] = useMemo(() => {
    const file = code?.files.find((item) => item.path === activePath);
    const toolItems: ColumnItem[] = (file?.symbols ?? [])
      .filter(
        (symbol) => symbol.kind === "function" && tools.includes(symbol.name),
      )
      .map((symbol) => ({
        key: `tool:${symbol.name}:${symbol.start}`,
        line: symbol.start,
        kind: "tool",
        name: symbol.name,
      }));
    const noteItems: ColumnItem[] = notes.map((note) => ({
      key: note.key,
      line: note.line,
      kind: "note",
      note,
    }));
    return [...noteItems, ...toolItems].sort(
      (a, b) => a.line - b.line || a.key.localeCompare(b.key),
    );
  }, [code, activePath, tools, notes]);

  const [focus, setFocus] = useState<Focus | null>(null);
  const [activeNote, setActiveNote] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const notesRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef(new Map<string, HTMLElement>());
  const [layout, setLayout] = useState<{ tops: number[]; height: number }>({
    tops: [],
    height: 0,
  });

  // A different lesson or file starts without stale highlights.
  useEffect(() => {
    setFocus(null);
    setActiveNote(null);
    setEvidence(null);
  }, [detail.id]);

  const measure = useCallback(() => {
    const frame = frameRef.current;
    const column = notesRef.current;
    if (!frame || !column) return;
    const base = column.getBoundingClientRect().top;
    const desired = items.map((item) => {
      const line = frame.querySelector(`[data-line="${item.line}"]`);
      return line ? line.getBoundingClientRect().top - base : 0;
    });
    const heights = items.map(
      (item) => itemRefs.current.get(item.key)?.offsetHeight ?? 0,
    );
    const tops = stackNotes(desired, heights);
    const height = tops.reduce(
      (max, top, index) => Math.max(max, top + heights[index]),
      0,
    );
    setLayout((previous) =>
      previous.height === height &&
      previous.tops.length === tops.length &&
      previous.tops.every((top, index) => Math.abs(top - tops[index]) < 0.5)
        ? previous
        : { tops, height },
    );
  }, [items]);

  useLayoutEffect(() => {
    measure();
  }, [measure, activeSource?.content]);

  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    if (frameRef.current) observer.observe(frameRef.current);
    if (notesRef.current) observer.observe(notesRef.current);
    return () => observer.disconnect();
  }, [measure]);

  // Scroll after the target file has rendered; reduced motion jumps instantly.
  useEffect(() => {
    if (!focus || focus.path !== activePath) return;
    frameRef.current
      ?.querySelector<HTMLElement>(`[data-line="${focus.start}"]`)
      ?.scrollIntoView({
        block: "center",
        behavior: reduced ? "auto" : "smooth",
      });
  }, [focus, activePath, reduced]);

  const jump = (path: string, start: number, end = start) => {
    const index = detail.sources.findIndex((source) => source.path === path);
    if (index < 0) return;
    if (index !== activeIndex) studio.setSource(index);
    setFocus({ path, start, end, nonce: Date.now() });
  };

  /** Only real events: select the latest tool_result of this tool in 实验, or say why there is none. */
  const openEvidence = (name: string, at: string) => {
    if (!studio.events.length) {
      setEvidence({ name, at, reason: "noRun" });
      return;
    }
    const index = latestToolResult(studio.events, name);
    if (index < 0) {
      setEvidence({ name, at, reason: "notCalled" });
      return;
    }
    setEvidence(null);
    if (index < studio.cursor) studio.selectEvent(index);
    else studio.seek(index + 1);
    requestScene("lab");
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
          <nav
            className="code-files"
            aria-label={t("files")}
            data-testid="code-files"
          >
            <ul>
              {detail.sources.map((file, index) => (
                <li key={file.path}>
                  <button
                    type="button"
                    data-testid="code-file"
                    data-path={file.path}
                    aria-current={index === activeIndex ? "true" : undefined}
                    title={file.path}
                    onClick={() => studio.setSource(index)}
                  >
                    <span className="code-file-name">
                      {basename(file.path)}
                    </span>
                    <span className="code-file-dir">{dirname(file.path)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
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
            <aside
              className="code-notes"
              data-testid="code-notes"
              aria-label={t("notes")}
              ref={notesRef}
              style={
                { "--notes-height": `${layout.height}px` } as CSSProperties
              }
            >
              {items.length === 0 && (
                <p className="code-notes-empty">{t("notesEmpty")}</p>
              )}
              {items.map((item, index) => (
                <div
                  key={item.key}
                  className="code-note-slot"
                  data-kind={item.kind}
                  ref={(element) => {
                    if (element) itemRefs.current.set(item.key, element);
                    else itemRefs.current.delete(item.key);
                  }}
                  style={
                    {
                      "--note-top": `${layout.tops[index] ?? 0}px`,
                      "--i": index,
                    } as CSSProperties
                  }
                >
                  {item.kind === "note" ? (
                    <button
                      type="button"
                      className="code-note"
                      data-testid="code-note"
                      data-line={item.line}
                      aria-pressed={activeNote === item.key}
                      aria-label={t("jumpToLine", { line: item.line })}
                      onClick={() => {
                        setActiveNote(item.key);
                        jump(activePath, item.line);
                      }}
                    >
                      <span className="code-note-line">
                        {t("noteLine", { line: item.line })}
                      </span>
                      <span className="code-note-text">{item.note.text}</span>
                    </button>
                  ) : (
                    <EvidenceButton
                      name={item.name}
                      at={item.key}
                      evidence={evidence}
                      onOpen={openEvidence}
                    />
                  )}
                </div>
              ))}
            </aside>
          </div>
        </div>
      ) : (
        <p className="learn-empty">{t("empty")}</p>
      )}
      <section className="learn-reference-section" data-testid="code-prompt">
        <span className="reading-eyebrow">{t("promptEyebrow")}</span>
        <h2>{t("promptTitle")}</h2>
        <p>{t("promptHelp")}</p>
        {detail.system_prompt ? (
          <div className="learn-code-frame code-prompt-frame">
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
        {tools.length > 0 && (
          <div className="code-tool-evidence">
            {tools.map((name) => (
              <EvidenceButton
                key={name}
                name={name}
                at={`tools:${name}`}
                evidence={evidence}
                onOpen={openEvidence}
              />
            ))}
          </div>
        )}
        <div className="learn-code-frame">
          <Code
            content={JSON.stringify(detail.tools, null, 2) ?? t("noTools")}
            language="json"
          />
        </div>
      </section>
      {decisions.length > 0 && (
        <section className="code-decisions" data-testid="code-decisions">
          <span className="reading-eyebrow">{t("decisions.eyebrow")}</span>
          <h2>{t("decisions.title")}</h2>
          {decisions.map((decision, index) => (
            <FadeContent
              key={decision.id}
              className="code-decision-reveal"
              delay={index * 0.08}
            >
              <GlareHover glareColor="185 138 255" glareOpacity={0.18}>
                <article className="code-decision" data-testid="code-decision">
                  <h3>{decision.title}</h3>
                  <div className="code-decision-chosen">
                    <h4>{t("decisions.chosen")}</h4>
                    <p>{decision.chosen}</p>
                  </div>
                  {decision.alternatives.length > 0 && (
                    <div className="code-decision-alternatives">
                      <h4>{t("decisions.alternatives")}</h4>
                      <ul>
                        {decision.alternatives.map((alternative) => (
                          <li key={alternative.id}>
                            <strong>{alternative.title}</strong>
                            <p>{alternative.why_not}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              </GlareHover>
            </FadeContent>
          ))}
        </section>
      )}
    </div>
  );
}
