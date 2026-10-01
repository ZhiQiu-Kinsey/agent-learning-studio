import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import GlideSelect from "./react-bits/GlideSelect";

type Theme = "light" | "dark" | "system";
const storageKey = "agent-lab-theme";
const parseTheme = (value: string | null | undefined): Theme =>
  value === "light" || value === "dark" ? value : "system";

export function ThemeSwitch() {
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
    <div className="theme-control" title="切换页面主题">
      <Icon size={16} aria-hidden="true" />
      <GlideSelect
        ariaLabel="页面主题"
        value={preference}
        options={[
          { value: "system", label: "跟随系统" },
          { value: "light", label: "浅色" },
          { value: "dark", label: "深色" },
        ]}
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
