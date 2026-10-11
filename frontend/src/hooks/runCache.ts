import type { Detail } from "../types";

/**
 * Which finished run answered which question, so coming back to a lesson does
 * not call the model again for the same thing. A run is reused only while the
 * lesson, the exercise, the question, the inputs, the system prompt, the tool
 * definitions, the run language and the lesson and platform code are all unchanged.
 *
 * The browser keeps only run ids and a hash of those inputs; the events stay
 * in the server's run store and are read back unchanged (replay is read-only).
 * If stored data is newer than this code or unreadable, the cache works in
 * memory and never overwrites it.
 */
export const runCacheStorageKey = "agent-lab-run-cache";
const VERSION = 1;
/** Plenty for every exercise of every lesson; the oldest entries drop off. */
const LIMIT = 80;

type Entry = { key: string; runId: string; at: string };
type StorageLike = Pick<Storage, "getItem" | "setItem">;

export function createRunCache(
  storage: StorageLike | undefined,
  storageKey = runCacheStorageKey,
) {
  let writable = !!storage;
  let entries = load();

  function load(): Entry[] {
    let raw: string | null = null;
    try {
      raw = storage?.getItem(storageKey) ?? null;
    } catch {
      writable = false;
      return [];
    }
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw) as {
        version?: unknown;
        entries?: unknown;
      };
      if (parsed?.version !== VERSION || !Array.isArray(parsed.entries))
        throw new Error("unknown run cache format");
      return parsed.entries.filter(
        (entry): entry is Entry =>
          !!entry &&
          typeof entry.key === "string" &&
          typeof entry.runId === "string" &&
          typeof entry.at === "string",
      );
    } catch {
      writable = false;
      return [];
    }
  }

  function persist() {
    if (!writable) return;
    try {
      storage!.setItem(
        storageKey,
        JSON.stringify({ version: VERSION, entries }),
      );
    } catch {
      writable = false;
    }
  }

  return {
    get(key: string): string | null {
      return entries.find((entry) => entry.key === key)?.runId ?? null;
    },
    remember(key: string, runId: string) {
      entries = [
        { key, runId, at: new Date().toISOString() },
        ...entries.filter((entry) => entry.key !== key),
      ].slice(0, LIMIT);
      persist();
    },
    forget(key: string) {
      entries = entries.filter((entry) => entry.key !== key);
      persist();
    },
  };
}

/** cyrb53: a fast, stable 53-bit string hash. Only compares inputs; protects nothing. */
export function hashText(text: string) {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let index = 0; index < text.length; index++) {
    const code = text.charCodeAt(index);
    h1 = Math.imul(h1 ^ code, 2654435761);
    h2 = Math.imul(h2 ^ code, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
}

/** JSON with object keys sorted, so `{a, b}` and `{b, a}` compare equal. */
export function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object")
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${stable((value as Record<string, unknown>)[key])}`,
      )
      .join(",")}}`;
  return JSON.stringify(value) ?? "null";
}

/** Everything a run's result depends on that the learner or the course can change, as one key. */
export function runKey(
  detail: Pick<Detail, "id" | "system_prompt" | "tools" | "sources" | "runtime_locale">,
  exerciseId: string,
  question: string,
  inputs: Record<string, unknown>,
) {
  // Fixtures only serve automated tests; lesson and platform code shape the run.
  const code = detail.sources
    .filter((source) => source.role !== "fixture")
    .map((source) => `${source.path}\n${source.content}`);
  return `${detail.id}:${exerciseId}:${hashText(
    stable([
      question,
      inputs,
      detail.system_prompt,
      detail.tools,
      code,
      detail.runtime_locale ?? null,
    ]),
  )}`;
}

function browserStorage() {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

export const runCache = createRunCache(
  typeof window === "undefined" ? undefined : browserStorage(),
);
