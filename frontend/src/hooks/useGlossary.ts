import { useEffect, useMemo, useState } from "react";
import { jsonFetch } from "../api";
import {
  buildMatcher,
  type GlossaryEntry,
  type GlossaryMatcher,
} from "../content/glossary/match";

export interface GlossaryData {
  schema_version: number;
  locale: string;
  terms: GlossaryEntry[];
}

// One request per page load (single source: curriculum/glossary.json via /api/glossary).
let pending: Promise<GlossaryData> | null = null;
let cached: GlossaryData | null = null;
const load = () =>
  (pending ??= jsonFetch<GlossaryData>("/api/glossary")
    .then((data) => (cached = data))
    .catch((error) => {
      pending = null;
      throw error;
    }));

/** Shared, cached glossary; null until loaded or when unavailable. */
export function useGlossary() {
  const [data, setData] = useState<GlossaryData | null>(cached);
  useEffect(() => {
    if (cached) return;
    let alive = true;
    load()
      .then((value) => alive && setData(value))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  return data;
}

const matchers = new WeakMap<GlossaryData, GlossaryMatcher | null>();

/** The glossary's matcher, built once per loaded glossary and shared. */
export function useGlossaryMatcher() {
  const data = useGlossary();
  return useMemo(() => {
    if (!data) return null;
    if (!matchers.has(data)) matchers.set(data, buildMatcher(data.terms));
    return matchers.get(data) ?? null;
  }, [data]);
}
