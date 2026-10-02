import { lazy, Suspense, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import { Button } from "../ui/button";
import type { CommandPaletteProps } from "./CommandPalette";
import "../../styles/command.css";

// cmdk and the command list load on first open.
const CommandPalette = lazy(() =>
  import("./CommandPalette").then((m) => ({ default: m.CommandPalette })),
);

const OPEN_EVENT = "agent-lab:command";

/** Opens the palette from anywhere (toolbar button, CTAs). */
export function openCommandPalette() {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

const isMac = () =>
  /mac|iphone|ipad/i.test(
    (navigator as Navigator & { userAgentData?: { platform?: string } })
      .userAgentData?.platform ?? navigator.platform,
  );

/** True for ⌘K on macOS and Ctrl+K elsewhere (either is accepted everywhere). */
export function isCommandHotkey(event: KeyboardEvent) {
  return (
    (event.metaKey || event.ctrlKey) &&
    !event.altKey &&
    !event.shiftKey &&
    event.key.toLowerCase() === "k"
  );
}

/** Toolbar trigger. Radix returns focus here when the palette closes. */
export function CommandButton() {
  const { t } = useTranslation("command");
  const shortcut = isMac() ? "⌘K" : "Ctrl K";
  return (
    <Button
      variant="outline"
      className="command-button"
      data-testid="app-command-button"
      aria-label={t("openHint", { shortcut })}
      aria-keyshortcuts="Meta+K Control+K"
      title={t("openHint", { shortcut })}
      onClick={openCommandPalette}
    >
      <Search size={15} aria-hidden="true" />
      <span className="command-button-label">{t("open")}</span>
      <kbd aria-hidden="true">{shortcut}</kbd>
    </Button>
  );
}

/** Mount point: hotkey listener plus the lazily loaded palette. */
export function CommandMenu(
  props: Omit<CommandPaletteProps, "open" | "onOpenChange">,
) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const show = () => {
      setLoaded(true);
      setOpen(true);
    };
    const onKey = (event: KeyboardEvent) => {
      if (!isCommandHotkey(event) || event.repeat) return;
      // Another modal (settings, course menu) keeps the keyboard.
      const other = document.querySelector(
        "[role='dialog'][data-state='open']:not([data-command-palette])",
      );
      if (other) return;
      event.preventDefault();
      setLoaded(true);
      setOpen((value) => !value);
    };
    window.addEventListener(OPEN_EVENT, show);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener(OPEN_EVENT, show);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  if (!loaded) return null;
  return (
    <Suspense fallback={null}>
      <CommandPalette {...props} open={open} onOpenChange={setOpen} />
    </Suspense>
  );
}
