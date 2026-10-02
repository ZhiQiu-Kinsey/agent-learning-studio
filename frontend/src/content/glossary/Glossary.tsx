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
import DecryptedText from "../../components/react-bits/DecryptedText";
import { useReducedMotion } from "../../motion";
import {
  assignFirstOccurrences,
  keywordKind,
  rehypeGlossary,
  splitCode,
  splitText,
  type GlossaryEntry,
  type GlossaryMatcher,
  type Segment,
} from "./match";
import "../../styles/learning-glossary.css";

/**
 * Glossary terms in lesson prose. A <GlossaryScope> gets the scope's texts in
 * reading order and decides, once, which text owns the first occurrence of
 * each term; <GlossaryText> / <GlossaryMarkdown> then mark only those. Without
 * a scope (or before the glossary loads) text renders unchanged.
 */

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
  const same = entry.zh.toLowerCase() === entry.en.toLowerCase();
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <span
          className="glossary-term"
          tabIndex={0}
          data-term={entry.id}
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
            {t("kicker")}
          </span>
          <strong className="glossary-card-title">
            {entry.zh}
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
          <span className="glossary-card-definition">{entry.definition}</span>
          {entry.first_lesson_number !== undefined && (
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

function useOwned(text: string) {
  const scope = useContext(ScopeContext);
  return {
    matcher: scope?.matcher ?? null,
    allowed: scope?.owners.get(text),
  };
}

/** Plain string with its owned terms marked. */
export function GlossaryText({ text }: { text: string }) {
  const { matcher, allowed } = useOwned(text);
  // Split once per text: code-like tokens first, then owned glossary terms.
  const segments = useMemo(() => {
    const remaining = new Set(allowed ?? []);
    return splitCode(text).flatMap<Segment | { code: string }>((piece) =>
      typeof piece !== "string"
        ? [piece]
        : matcher && remaining.size
          ? splitText(piece, matcher, remaining)
          : [piece],
    );
  }, [matcher, allowed, text]);
  return (
    <>
      {segments.map((segment, index) => {
        if (typeof segment === "string") return segment;
        if ("code" in segment) {
          const { kind, role } = keywordKind(segment.code);
          return (
            <code
              key={index}
              className="code-keyword"
              data-keyword={kind}
              data-role={role}
            >
              {segment.code}
            </code>
          );
        }
        return (
          <GlossaryTerm key={index} entry={segment.entry}>
            {segment.text}
          </GlossaryTerm>
        );
      })}
    </>
  );
}

/** Inline code: same text, coloured by what it names, sweep on hover. */
function CodeKeyword(props: ComponentProps<"code"> & { node?: unknown }) {
  const { node: _node, ...rest } = props;
  const kind = (rest as Record<string, unknown>)["data-keyword"];
  if (!kind) return <code {...rest} />;
  return <code {...rest} className={`code-keyword ${rest.className ?? ""}`} />;
}

/** Markdown with owned terms marked and inline code styled as keywords. */
export function GlossaryMarkdown({ children }: { children: string }) {
  const { matcher, allowed } = useOwned(children);
  const plugins = useMemo(
    () =>
      [[rehypeGlossary, { matcher, allowed }]] as ComponentProps<
        typeof Markdown
      >["rehypePlugins"],
    [matcher, allowed],
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
  return (
    <Markdown rehypePlugins={plugins} components={components}>
      {children}
    </Markdown>
  );
}
