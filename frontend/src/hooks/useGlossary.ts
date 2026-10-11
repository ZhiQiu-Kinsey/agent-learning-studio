import { useEffect, useMemo, useState } from "react";
import { jsonFetch } from "../api";
import {
  buildMatcher,
  type GlossaryEntry,
  type GlossaryMatcher,
} from "../content/glossary/match";
import { createLanguageCache } from "../lib/languageCache";
import { useContentLanguage } from "./useContentLanguage";

export interface GlossaryData {
  schema_version: number;
  locale: string;
  /** Requested vs. actually served language (definitions fall back per term). */
  i18n?: { requested: string; locale: string };
  terms: GlossaryEntry[];
}

// One request per language (single source: curriculum/glossary.json via /api/glossary).
const glossaries = createLanguageCache((language) =>
  jsonFetch<GlossaryData>("/api/glossary", undefined, language),
);

/**
 * Shared, cached glossary in the UI language; null until loaded or when
 * unavailable. After a language switch the previous glossary stays until the
 * new one arrives.
 */
export function useGlossary() {
  const language = useContentLanguage();
  const [data, setData] = useState<GlossaryData | null>(
    () => glossaries.peek(language) ?? null,
  );
  useEffect(() => {
    const hit = glossaries.peek(language);
    if (hit) {
      setData(hit);
      return;
    }
    let alive = true;
    glossaries
      .load(language)
      .then((value) => alive && setData(value))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [language]);
  return data;
}

const matchers = new WeakMap<GlossaryData, GlossaryMatcher | null>();

/** The glossary's matcher, built once per loaded glossary and shared. */
export function useGlossaryMatcher() {
  const data = useGlossary();
  return useMemo(() => {
    if (!data) return null;
    if (!matchers.has(data))
      matchers.set(
        data,
        buildMatcher(data.terms, data.i18n?.requested ?? data.locale),
      );
    return matchers.get(data) ?? null;
  }, [data]);
}
