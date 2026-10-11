import {
  createContext,
  useContext,
  useMemo,
  type ComponentProps,
  type ReactNode,
} from "react";
import Markdown, { type Components } from "react-markdown";
import { Tooltip } from "radix-ui";
import { useTranslation } from "react-i18next";
import { useGlossaryMatcher } from "../../hooks/useGlossary";
import {
  useContentLanguage,
  useFallbackLang,
} from "../../hooks/useContentLanguage";
import { isChineseText } from "../../i18n/textLanguage";
import DecryptedText from "../../components/react-bits/DecryptedText";
import { useReducedMotion } from "../../motion";
import {
  assignFirstOccurrences,
  buildNamePattern,
  isCodeShaped,
  isEnglishProse,
  keywordKind,
  rehypeGlossary,
  splitProse,
  type GlossaryEntry,
  type GlossaryMatcher,
} from "./match";
import { termTier, useVocabulary, VocabularyContext } from "./vocabulary";
import "../../styles/learning-glossary.css";

/**
 * Glossary terms in lesson prose. A <GlossaryScope> gets the scope's texts in
 * reading order and decides, once, which text owns the first occurrence of
 * each term; <GlossaryText> / <GlossaryMarkdown> then mark only those. Without
 * a scope (or before the glossary loads) text renders unchanged.
 *
 * <LessonVocabulary> wraps a whole lesson page: it tells terms which lesson
 * they are read in, and turns the lesson's own code names into inline code,
 * with the lesson's note (if any) as a hover card.
 */

export function LessonVocabulary({
  lessonId,
  codeNames,
  notes,
  children,
}: {
  lessonId: string;
  codeNames: readonly string[];
  notes: readonly { name: string; note: string }[];
  children: ReactNode;
}) {
  const signature = codeNames.join("\u0000");
  const [names, latinNames] = useMemo(
    () => [
      buildNamePattern(codeNames),
      buildNamePattern(codeNames.filter(isCodeShaped)),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signature],
  );
  const value = useMemo(
    () => ({
      lessonId,
      names,
      latinNames,
      notes: new Map(notes.map((item) => [item.name, item.note])),
    }),
    [lessonId, names, latinNames, notes],
  );
  return (
    <VocabularyContext.Provider value={value}>
      <Tooltip.Provider delayDuration={180} skipDelayDuration={240}>
        {children}
      </Tooltip.Provider>
    </VocabularyContext.Provider>
  );
}

interface Scope {
  matcher: GlossaryMatcher | null;
  owners: Map<string, Set<string>>;
}
const ScopeContext = createContext<Scope | null>(null);

export function GlossaryScope({
  texts,
  children,
}: {
  texts: readonly string[];
  children: ReactNode;
}) {
  const matcher = useGlossaryMatcher();
  // Keyed by content so re-renders with equal texts reuse the assignment.
  const signature = texts.join("\u0000");
  const owners = useMemo(
    () => (matcher ? assignFirstOccurrences(texts, matcher) : new Map()),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [matcher, signature],
  );
  const scope = useMemo(() => ({ matcher, owners }), [matcher, owners]);
  return (
    <ScopeContext.Provider value={scope}>
      <Tooltip.Provider delayDuration={180} skipDelayDuration={240}>
        {children}
      </Tooltip.Provider>
    </ScopeContext.Provider>
  );
}

/** A term: gradient underline at rest; text effect + definition card on hover/focus. */
export function GlossaryTerm({
  entry,
  children,
}: {
  entry: GlossaryEntry;
  children: ReactNode;
}) {
  const { t } = useTranslation("blocks", { keyPrefix: "glossary" });
  const reduced = useReducedMotion();
  const { lessonId } = useVocabulary();
  const tier = termTier(entry, lessonId);
  // A non-source glossary carries `term`: the card shows only that name, no
  // Chinese, and marks a definition that fell back to Chinese with its language.
  const localized = entry.term !== undefined;
  const same = localized || entry.zh.toLowerCase() === entry.en.toLowerCase();
  const kicker =
    tier === "new"
      ? t("kickerNew")
      : tier === "background"
        ? t("kickerBackground")
        : t("kicker");
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <span
          className="glossary-term"
          tabIndex={0}
          data-term={entry.id}
          data-tier={tier}
          data-testid="glossary-term"
        >
          {children}
        </span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          className="glossary-card"
          side="top"
          align="center"
          sideOffset={10}
          collisionPadding={14}
          data-testid="glossary-card"
        >
          <span className="glossary-card-kicker" aria-hidden="true">
            {kicker}
          </span>
          <strong className="glossary-card-title">
            {localized ? entry.term : entry.zh}
            {!same && (
              <span className="glossary-card-en">
                {t("enBefore")}
                {reduced ? (
                  entry.en
                ) : (
                  <DecryptedText text={entry.en} speed={28} />
                )}
                {t("enAfter")}
              </span>
            )}
          </strong>
          <span
            className="glossary-card-definition"
            lang={
              localized && entry.definition_locale
                ? entry.definition_locale
                : undefined
            }
          >
            {entry.definition}
          </span>
          {tier !== "new" && entry.first_lesson_number !== undefined && (
            <span className="glossary-card-first">
              {t("firstLesson", { number: entry.first_lesson_number })}
            </span>
          )}
          <Tooltip.Arrow
            className="glossary-card-arrow"
            width={12}
            height={6}
          />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/**
 * The code-name pattern for one string: all source names in Chinese text,
 * only code-shaped ones in English text (a plain word like "is" stays prose).
 */
function useNames(text: string) {
  const { names, latinNames } = useVocabulary();
  const language = useContentLanguage();
  return !isEnglishProse(language) || isChineseText(text)
    ? names
    : (latinNames ?? null);
}

function useOwned(text: string) {
  const scope = useContext(ScopeContext);
  return {
    matcher: scope?.matcher ?? null,
    allowed: scope?.owners.get(text),
  };
}

/** Inline code coloured by what it names; the lesson's note, if any, as a hover card. */
export function CodeName({
  code,
  className,
  ...rest
}: { code: string } & ComponentProps<"code">) {
  const { t } = useTranslation("blocks", { keyPrefix: "glossary" });
  const { notes } = useVocabulary();
  const { kind, role } = keywordKind(code);
  const note = notes.get(code.trim());
  const chip = (
    <code
      {...rest}
      className={`code-keyword ${className ?? ""}`.trim()}
      data-keyword={kind}
      data-role={role}
      data-noted={note ? "" : undefined}
      tabIndex={note ? 0 : undefined}
      data-testid={note ? "code-note-trigger" : undefined}
    >
      {code}
    </code>
  );
  if (!note) return chip;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{chip}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          className="glossary-card glossary-card-code"
          side="top"
          align="center"
          sideOffset={10}
          collisionPadding={14}
          data-testid="code-note-card"
        >
          <span className="glossary-card-kicker" aria-hidden="true">
            {t("codeKicker")}
          </span>
          <strong className="glossary-card-title glossary-card-code-name">
            {code}
          </strong>
          <span className="glossary-card-definition">{note}</span>
          <Tooltip.Arrow
            className="glossary-card-arrow"
            width={12}
            height={6}
          />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/** Plain string with its owned terms marked and code names as inline code. */
export function GlossaryText({ text }: { text: string }) {
  const { matcher, allowed } = useOwned(text);
  const names = useNames(text);
  const lang = useFallbackLang()(text);
  const pieces = useMemo(
    () => splitProse(text, matcher, new Set(allowed ?? []), names),
    [matcher, allowed, names, text],
  );
  const body = pieces.map((piece, index) => {
    if (typeof piece === "string") return piece;
    if ("code" in piece) return <CodeName key={index} code={piece.code} />;
    return (
      <GlossaryTerm key={index} entry={piece.entry}>
        {piece.text}
      </GlossaryTerm>
    );
  });
  // A string that fell back to Chinese under another UI language says so.
  return lang ? <span lang={lang}>{body}</span> : <>{body}</>;
}

/** Inline code in markdown: same text, coloured by what it names, note on hover. */
function CodeKeyword(props: ComponentProps<"code"> & { node?: unknown }) {
  const { node: _node, children, ...rest } = props;
  const kind = (rest as Record<string, unknown>)["data-keyword"];
  if (!kind || typeof children !== "string")
    return <code {...rest}>{children}</code>;
  const {
    "data-keyword": _kind,
    "data-role": _role,
    ...others
  } = rest as Record<string, unknown>;
  return <CodeName {...(others as ComponentProps<"code">)} code={children} />;
}

/** Markdown with owned terms marked and inline code styled as keywords. */
export function GlossaryMarkdown({ children }: { children: string }) {
  const { matcher, allowed } = useOwned(children);
  const names = useNames(children);
  const plugins = useMemo(
    () =>
      [[rehypeGlossary, { matcher, allowed, names }]] as ComponentProps<
        typeof Markdown
      >["rehypePlugins"],
    [matcher, allowed, names],
  );
  const components = useMemo<Components>(
    () => ({
      code: CodeKeyword,
      span: ({ node: _node, ...props }) => {
        const id = (props as Record<string, unknown>)["data-glossary"];
        const entry =
          typeof id === "string" ? matcher?.byId.get(id) : undefined;
        return entry ? (
          <GlossaryTerm entry={entry}>{props.children}</GlossaryTerm>
        ) : (
          <span {...props} />
        );
      },
    }),
    [matcher],
  );
  const lang = useFallbackLang()(children);
  const body = (
    <Markdown rehypePlugins={plugins} components={components}>
      {children}
    </Markdown>
  );
  // display: contents keeps the markdown's own block layout.
  return lang ? (
    <div lang={lang} className="lang-fallback">
      {body}
    </div>
  ) : (
    body
  );
}
