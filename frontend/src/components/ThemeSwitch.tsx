import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import GlideSelect from "./react-bits/GlideSelect";

export type Theme = "light" | "dark" | "system";
const storageKey = "agent-lab-theme";
const parseTheme = (value: string | null | undefined): Theme =>
  value === "light" || value === "dark" ? value : "system";
export const themePreferences = ["system", "light", "dark"] as const;

/** Current choice, for entry points outside the switch (command palette). */
export const themePreferenceNow = (): Theme =>
  parseTheme(document.documentElement.dataset.themePreference);

/** Changes the theme from elsewhere; every mounted ThemeSwitch follows via its storage listener. */
export function setThemePreference(theme: Theme) {
  try {
    localStorage.setItem(storageKey, theme);
  } catch {
    /* The event below still updates this session. */
  }
  window.dispatchEvent(
    new StorageEvent("storage", { key: storageKey, newValue: theme }),
  );
}

export function ThemeSwitch() {
  const { t } = useTranslation();
  const [preference, setPreference] = useState<Theme>(() =>
    parseTheme(document.documentElement.dataset.themePreference),
  );

  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved =
        preference === "system"
          ? media.matches
            ? "dark"
            : "light"
          : preference;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.dataset.themePreference = preference;
      document.documentElement.style.colorScheme = resolved;
      document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute("content", resolved === "dark" ? "#111316" : "#f4f5f1");
    };
    apply();
    media.addEventListener("change", apply);
    const sync = (event: StorageEvent) => {
      if (event.key === storageKey || event.key === null)
        setPreference(parseTheme(event.newValue));
    };
    window.addEventListener("storage", sync);
    return () => {
      media.removeEventListener("change", apply);
      window.removeEventListener("storage", sync);
    };
  }, [preference]);

  const Icon =
    preference === "dark" ? Moon : preference === "light" ? Sun : Monitor;
  return (
    <div className="theme-control" title={t("theme.control")}>
      <Icon size={16} aria-hidden="true" />
      <GlideSelect
        ariaLabel={t("theme.label")}
        value={preference}
        options={themePreferences.map((value) => ({
          value,
          label: t(`theme.${value}`),
        }))}
        size="sm"
        align="right"
        menuWidth={136}
        accentColor="var(--text)"
        surfaceColor="var(--surface)"
        highlightColor="var(--surface-muted)"
        textColor="var(--text)"
        onChange={(value) => {
          const next = parseTheme(value);
          setPreference(next);
          try {
            localStorage.setItem(storageKey, next);
          } catch {
            /* Keep the session choice. */
          }
        }}
      />
    </div>
  );
}
