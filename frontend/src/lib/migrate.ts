/**
 * Ordered migration ladder for versioned records. Each step upgrades exactly
 * one version. Missing steps are an error; data newer than the code is left
 * untouched and reported so callers can avoid overwriting it.
 */
export interface MigrationStep {
  from: number;
  to: number;
  up: (data: Record<string, unknown>) => Record<string, unknown>;
}

export type MigrationResult<T> =
  | { status: "current" | "migrated"; data: T }
  | { status: "newer"; version: number };

export function migrate<T>(
  data: Record<string, unknown>,
  current: number,
  steps: readonly MigrationStep[],
): MigrationResult<T> {
  let version = typeof data.version === "number" ? data.version : 0;
  if (version > current) return { status: "newer", version };
  const start = version;
  let value = data;
  while (version < current) {
    const step = steps.find((candidate) => candidate.from === version);
    if (!step || step.to !== version + 1)
      throw new Error(`no migration from version ${version} to ${version + 1}`);
    value = { ...step.up(value), version: step.to };
    version = step.to;
  }
  return { status: start === current ? "current" : "migrated", data: value as T };
}
