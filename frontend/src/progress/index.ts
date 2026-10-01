import { useSyncExternalStore } from "react";
import { createProgressStore, progressStorageKey } from "./store";

export * from "./model";
export { createProgressStore, progressStorageKey } from "./store";

function browserStorage() {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

export const progress = createProgressStore(browserStorage());

window.addEventListener("storage", (event) => {
  if (event.key === progressStorageKey || event.key === null) progress.reload();
});

export function useProgress() {
  return useSyncExternalStore(progress.subscribe, progress.get, progress.get);
}
