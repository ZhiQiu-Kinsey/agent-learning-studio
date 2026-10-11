/**
 * Compact form of a provider display name for narrow screens: the trailing
 * qualifier in parentheses (ASCII or full-width) is dropped, so
 * "Bailian (raw HTTP)" becomes "Bailian". Names without one are unchanged.
 */
export function shortProviderName(name: string) {
  const short = name.replace(/\s*[(（][^()（）]*[)）]\s*$/u, "");
  return short.trim() || name;
}
