import { useEffect, useRef, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { motionLevelNow } from "../motion";
import GlideSelect from "./react-bits/GlideSelect";

export type Theme = "light" | "dark" | "system";
const storageKey = "agent-lab-theme";
const parseTheme = (value: string | null | undefined): Theme =>
  value === "light" || value === "dark" ? value : "system";
export const themePreferences = ["system", "light", "dark"] as const;

const resolveTheme = (preference: Theme) =>
  preference === "system"
    ? matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
    : preference;

function applyTheme(preference: Theme) {
  const resolved = resolveTheme(preference);
  const root = document.documentElement;
  root.dataset.theme = resolved;
  root.dataset.themePreference = preference;
  root.style.colorScheme = resolved;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", resolved === "dark" ? "#111316" : "#f4f5f1");
}

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void) => { ready: Promise<void> };
};

/**
 * Applies a theme preference. When the visible theme actually changes and motion
 * is full, the new theme spreads as a circle from `origin` (View Transitions);
 * static motion or browsers without the API switch instantly.
 */
function transitionTheme(next: Theme, origin?: { x: number; y: number }) {
  const doc = document as ViewTransitionDocument;
  const changes = resolveTheme(next) !== doc.documentElement.dataset.theme;
  if (!changes || !doc.startViewTransition || motionLevelNow() !== "full") {
    applyTheme(next);
    return;
  }
  const x = origin?.x ?? window.innerWidth / 2;
  const y = origin?.y ?? 0;
  const radius = Math.hypot(
    Math.max(x, window.innerWidth - x),
    Math.max(y, window.innerHeight - y),
  );
  doc
    .startViewTransition(() => applyTheme(next))
    .ready.then(() => {
      doc.documentElement.animate(
        {
          clipPath: [
            `circle(0px at ${x}px ${y}px)`,
            `circle(${radius}px at ${x}px ${y}px)`,
          ],
        },
        {
          duration: 720,
          easing: "cubic-bezier(0.45, 0, 0.2, 1)",
          pseudoElement: "::view-transition-new(root)",
        },
      );
    })
    .catch(() => {
      /* The theme is applied either way. */
    });
}

/** Current choice, for entry points outside the switch (command palette). */
export const themePreferenceNow = (): Theme =>
  parseTheme(document.documentElement.dataset.themePreference);

/** Changes the theme from elsewhere; every mounted ThemeSwitch follows via its storage listener. */
export function setThemePreference(theme: Theme) {
  transitionTheme(theme);
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
  const ref = useRef<HTMLDivElement>(null);
  const [preference, setPreference] = useState<Theme>(() =>
    parseTheme(document.documentElement.dataset.themePreference),
  );

  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => applyTheme(preference);
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
    <div className="theme-control" title={t("theme.control")} ref={ref}>
      <Icon
        key={preference}
        size={16}
        aria-hidden="true"
        className="theme-control-icon"
      />
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
          const box = ref.current?.getBoundingClientRect();
          transitionTheme(
            next,
            box && {
              x: box.left + box.width / 2,
              y: box.top + box.height / 2,
            },
          );
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
