import { migrate } from "../lib/migrate";
import {
  emptyProgress,
  progressMigrations,
  PROGRESS_VERSION,
  reduceProgress,
  type ProgressAction,
  type ProgressRecord,
} from "./model";

export const progressStorageKey = "agent-lab-progress";

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

/**
 * localStorage-backed progress store. If stored data is newer than this code
 * (or unreadable) the store works in memory and never overwrites it.
 */
export function createProgressStore(
  storage: StorageLike | undefined,
  key = progressStorageKey,
) {
  let writable = !!storage;
  let state = load();
  const listeners = new Set<() => void>();

  function load(): ProgressRecord {
    let raw: string | null = null;
    try {
      raw = storage?.getItem(key) ?? null;
    } catch {
      writable = false;
      return emptyProgress();
    }
    if (!raw) return emptyProgress();
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
        throw new Error("progress must be an object");
      const result = migrate<ProgressRecord>(
        parsed,
        PROGRESS_VERSION,
        progressMigrations,
      );
      if (result.status === "newer") {
        writable = false;
        return emptyProgress();
      }
      return result.data;
    } catch {
      // Keep the unreadable original for inspection instead of replacing it.
      writable = false;
      return emptyProgress();
    }
  }

  function persist() {
    if (!writable) return;
    try {
      storage!.setItem(key, JSON.stringify(state));
    } catch {
      /* Quota or privacy mode: keep working in memory. */
    }
  }

  return {
    get: () => state,
    get writable() {
      return writable;
    },
    dispatch(action: ProgressAction) {
      const next = reduceProgress(state, action);
      if (next === state) return;
      state = next;
      if (action.type === "cleared" && writable) {
        try {
          storage!.removeItem(key);
        } catch {
          /* Nothing stored to clear. */
        }
      } else persist();
      listeners.forEach((listener) => listener());
    },
    /** Re-read after another tab changed the key. */
    reload() {
      writable = !!storage;
      state = load();
      listeners.forEach((listener) => listener());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

export type ProgressStore = ReturnType<typeof createProgressStore>;
