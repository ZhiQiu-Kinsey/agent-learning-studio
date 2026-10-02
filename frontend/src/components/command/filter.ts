import { defaultFilter } from "cmdk";

/**
 * Exact, prefix and substring hits on the value or any keyword (slug, alias,
 * number, title) rank above cmdk's fuzzy score, so typing "2" or a slug puts
 * that lesson first while loose fuzzy matches remain further down.
 */
export function paletteFilter(
  value: string,
  search: string,
  keywords: string[] = [],
): number {
  const query = search.trim().toLowerCase();
  if (!query) return 1;
  const fields = [value, ...keywords].map((field) => field.toLowerCase());
  if (fields.includes(query)) return 1;
  if (fields.some((field) => field.startsWith(query))) return 0.9;
  if (fields.some((field) => field.includes(query))) return 0.8;
  return defaultFilter(value, search, keywords) * 0.5;
}
