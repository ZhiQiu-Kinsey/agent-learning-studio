export type SelectorCounts = {
  cjkSelectors: number;
  cjkAssertions: number;
  classSelectors: number;
};
export const e2eDir: string;
export const baselinePath: string;
export function countSelectors(text: string, fileName?: string): SelectorCounts;
export function scanSpecs(dir?: string): Record<string, SelectorCounts>;
export function totals(scan: Record<string, SelectorCounts>): SelectorCounts;
