/**
 * Glossary matching for lesson prose. Pure functions: build one matcher per
 * glossary, find which text owns the first occurrence of each term, and split
 * a string or a markdown tree so only those occurrences get marked. Text is
 * never rewritten; marked spans keep the original characters.
 */

export interface GlossaryEntry {
  id: string;
  zh: string;
  en: string;
  /** concept: course concept; background: side knowledge, hover card only. */
  kind?: "concept" | "background";
  definition: string;
  aliases: string[];
  /** Longer phrases whose inner name is not this term (验收器 is not 验收标准). */
  not_in?: string[];
  display?: string;
  first_lesson?: string;
  first_lesson_number?: number;
}

export interface GlossaryMatcher {
  regex: RegExp;
  /** Lower-cased surface form (spaces collapsed) -> entry; null for a blocked phrase. */
  forms: Map<string, GlossaryEntry | null>;
  byId: Map<string, GlossaryEntry>;
}

export type Segment = string | { entry: GlossaryEntry; text: string };

const LATIN_EDGE = /[A-Za-z0-9]/;
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const normalise = (value: string) => value.toLowerCase().replace(/\s+/g, " ");

/**
 * One alternation for every zh / en / alias form; longest forms win. Chinese
 * has no word boundaries, so a term lists the longer phrases (not_in) that
 * contain its name with another meaning; those phrases match first and mark
 * nothing.
 */
export function buildMatcher(
  entries: readonly GlossaryEntry[],
): GlossaryMatcher | null {
  const forms = new Map<string, GlossaryEntry | null>();
  for (const entry of entries)
    for (const form of [entry.zh, entry.en, ...(entry.aliases ?? [])]) {
      const key = normalise(form.trim());
      if (key && !forms.has(key)) forms.set(key, entry);
    }
  for (const entry of entries)
    for (const phrase of entry.not_in ?? []) {
      const key = normalise(phrase.trim());
      if (key && !forms.has(key)) forms.set(key, null);
    }
  if (!forms.size) return null;
  const pattern = [...forms.keys()]
    .sort((a, b) => b.length - a.length)
    .map((form) => {
      // Latin edges need word boundaries ("Token" must not match "tokens").
      const head = LATIN_EDGE.test(form[0]) ? "(?<![A-Za-z0-9_])" : "";
      const tail = LATIN_EDGE.test(form[form.length - 1])
        ? "(?![A-Za-z0-9_])"
        : "";
      return head + form.split(" ").map(escape).join("\\s*") + tail;
    })
    .join("|");
  return {
    regex: new RegExp(pattern, "giu"),
    forms,
    byId: new Map(entries.map((entry) => [entry.id, entry])),
  };
}

const lookup = (matcher: GlossaryMatcher, text: string) =>
  matcher.forms.get(normalise(text)) ?? undefined;

/**
 * Code-like tokens written as plain prose (lesson content has no backticks):
 * `name=value`, dotted / indexed access, snake_case names, optional short call
 * parentheses — e.g. role=tool, function.name, tool_calls[0].function,
 * tool_call_id, add_numbers(19, 23), messages[3].
 */
const CODE_TOKEN =
  /(?<![\w.$])(?:[a-z_]\w*=[\w"'.-]+|[A-Za-z_]\w*(?:\[\d+\])?(?:\.[A-Za-z_]\w*(?:\[\d+\])?)+(?:\([^()\n]{0,30}\))?|[A-Za-z_]\w*_\w*(?:\[\d+\])*(?:\.[A-Za-z_]\w*)*(?:\([^()\n]{0,30}\))?|[A-Za-z_]\w*\[\d+\](?:\.[A-Za-z_]\w*)*)(?!\w)/g;

/** Split plain prose into text and code-like tokens (text is never changed). */
export function splitCode(text: string): (string | { code: string })[] {
  const pieces: (string | { code: string })[] = [];
  let last = 0;
  for (const match of text.matchAll(CODE_TOKEN)) {
    const start = match.index ?? 0;
    if (start > last) pieces.push(text.slice(last, start));
    pieces.push({ code: match[0] });
    last = start + match[0].length;
  }
  if (last < text.length) pieces.push(text.slice(last));
  return pieces;
}

/**
 * Bare code names (evidence, stop, Final Answer) that the lesson's own source
 * defines. The server lists them per lesson, minus glossary names; longest
 * names win, and a name never matches inside a longer word or identifier.
 */
export function buildNamePattern(names: readonly string[]): RegExp | null {
  const forms = [...new Set(names.filter((name) => name.trim()))].sort(
    (a, b) => b.length - a.length,
  );
  if (!forms.length) return null;
  return new RegExp(
    `(?<![\\w.$-])(?:${forms.map(escape).join("|")})(?![\\w-]|\\.\\w)`,
    "g",
  );
}

/** Split plain text into text and code-name pieces (text is never changed). */
export function splitNames(
  text: string,
  pattern: RegExp | null,
): (string | { code: string })[] {
  if (!pattern) return [text];
  const pieces: (string | { code: string })[] = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > last) pieces.push(text.slice(last, start));
    pieces.push({ code: match[0] });
    last = start + match[0].length;
  }
  if (last < text.length) pieces.push(text.slice(last));
  return pieces;
}

/** Markdown source with code spans, code-like tokens and link targets blanked out. */
export function plainOf(markdown: string) {
  return markdown
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`\n]*`/g, " ")
    .replace(/\]\([^)]*\)/g, "] ")
    .replace(CODE_TOKEN, " ");
}

/** Term ids in order of first appearance in one text. */
export function termsIn(text: string, matcher: GlossaryMatcher) {
  const ids: string[] = [];
  for (const match of plainOf(text).matchAll(matcher.regex)) {
    const entry = lookup(matcher, match[0]);
    if (entry && !ids.includes(entry.id)) ids.push(entry.id);
  }
  return ids;
}

/**
 * Walk texts in reading order; each term belongs to the first text that uses
 * it. Returns text -> term ids to mark there (texts without new terms omitted).
 */
export function assignFirstOccurrences(
  texts: readonly string[],
  matcher: GlossaryMatcher,
) {
  const seen = new Set<string>();
  const owners = new Map<string, Set<string>>();
  for (const text of texts) {
    if (!text || owners.has(text)) continue;
    const fresh = termsIn(text, matcher).filter((id) => !seen.has(id));
    if (!fresh.length) continue;
    fresh.forEach((id) => seen.add(id));
    owners.set(text, new Set(fresh));
  }
  return owners;
}

/**
 * Split plain text; only the first hit of each id in `remaining` is marked and
 * removed from the set (so one set can be threaded through a markdown tree).
 */
export function splitText(
  text: string,
  matcher: GlossaryMatcher,
  remaining: Set<string>,
): Segment[] {
  if (!remaining.size) return [text];
  const segments: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(matcher.regex)) {
    const entry = lookup(matcher, match[0]);
    if (!entry || !remaining.has(entry.id)) continue;
    remaining.delete(entry.id);
    const start = match.index ?? 0;
    if (start > last) segments.push(text.slice(last, start));
    segments.push({ entry, text: match[0] });
    last = start + match[0].length;
    if (!remaining.size) break;
  }
  if (last < text.length) segments.push(text.slice(last));
  return segments;
}

/* ---------- inline code keywords ---------- */

export type KeywordKind = "role" | "field" | "call" | "literal" | "code";

/** Classify inline code by what it names, for colour only; text is untouched. */
export function keywordKind(code: string): {
  kind: KeywordKind;
  role?: string;
} {
  const value = code.trim();
  const role =
    /^(?:role\s*[=:]\s*)?["']?(system|user|assistant|tool)["']?$/i.exec(value);
  if (role) return { kind: "role", role: role[1].toLowerCase() };
  if (/^[\w.]+\(.*\)$/.test(value)) return { kind: "call" };
  if (
    /^(?:-?\d[\d.]*|true|false|null|none|True|False|None|".*"|'.*')$/.test(
      value,
    )
  )
    return { kind: "literal" };
  if (/^[A-Za-z_][\w]*(?:[.[\]"'\w]*)?$/.test(value) && /[_.[]/.test(value))
    return { kind: "field" };
  return { kind: "code" };
}

/* ---------- markdown (hast) ---------- */

interface HastText {
  type: "text";
  value: string;
}
interface HastElement {
  type: "element";
  tagName: string;
  properties?: Record<string, unknown>;
  children: HastNode[];
}
type HastNode =
  HastText | HastElement | { type: string; children?: HastNode[] };

const SKIP = new Set(["code", "pre", "a", "kbd"]);

function keywordElement(code: string): HastElement {
  const { kind, role } = keywordKind(code);
  return {
    type: "element",
    tagName: "code",
    properties: { dataKeyword: kind, ...(role ? { dataRole: role } : {}) },
    children: [{ type: "text", value: code }],
  };
}

export type ProsePiece = Segment | { code: string };

/**
 * One pass over plain prose, in precedence order: code-like tokens, then the
 * owned glossary first occurrences, then the lesson's bare code names.
 */
export function splitProse(
  text: string,
  matcher: GlossaryMatcher | null,
  remaining: Set<string>,
  names: RegExp | null,
): ProsePiece[] {
  return splitCode(text).flatMap<ProsePiece>((piece) => {
    if (typeof piece !== "string") return [piece];
    const segments =
      matcher && remaining.size
        ? splitText(piece, matcher, remaining)
        : [piece];
    return segments.flatMap<ProsePiece>((segment) =>
      typeof segment === "string" ? splitNames(segment, names) : [segment],
    );
  });
}

/**
 * rehype plugin: wrap the allowed first occurrences in
 * `<span data-glossary="id">`, turn bare code names into inline code and tag
 * inline code with its keyword kind.
 */
export function rehypeGlossary(options: {
  matcher: GlossaryMatcher | null;
  allowed?: ReadonlySet<string>;
  names?: RegExp | null;
}) {
  return (tree: HastNode) => {
    const remaining = new Set(options.allowed ?? []);
    const visit = (node: HastNode, parent: HastElement | null) => {
      if (node.type === "element") {
        const element = node as HastElement;
        if (element.tagName === "code" && parent?.tagName !== "pre") {
          const text = element.children
            .map((child) =>
              child.type === "text" ? (child as HastText).value : "",
            )
            .join("");
          const { kind, role } = keywordKind(text);
          element.properties = {
            ...element.properties,
            dataKeyword: kind,
            ...(role ? { dataRole: role } : {}),
          };
        }
        if (SKIP.has(element.tagName)) return;
      }
      const children = (node as { children?: HastNode[] }).children;
      if (!children) return;
      const next: HastNode[] = [];
      for (const child of children) {
        if (child.type === "text") {
          const pieces = splitProse(
            (child as HastText).value,
            options.matcher,
            remaining,
            options.names ?? null,
          );
          for (const piece of pieces)
            next.push(
              typeof piece === "string"
                ? { type: "text", value: piece }
                : "code" in piece
                  ? keywordElement(piece.code)
                  : {
                      type: "element",
                      tagName: "span",
                      properties: { dataGlossary: piece.entry.id },
                      children: [{ type: "text", value: piece.text }],
                    },
            );
        } else {
          visit(
            child,
            node.type === "element" ? (node as HastElement) : parent,
          );
          next.push(child);
        }
      }
      (node as { children: HastNode[] }).children = next;
    };
    visit(tree, null);
  };
}
