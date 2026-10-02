import { useSyncExternalStore } from "react";

export type ResolvedTheme = "light" | "dark";

const read = (): ResolvedTheme =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "light";

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}

/** The theme actually applied (<html data-theme>), after resolving "system". */
export const useResolvedTheme = () =>
  useSyncExternalStore(subscribe, read, () => "light" as const);
