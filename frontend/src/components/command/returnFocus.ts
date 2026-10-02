import { useRef } from "react";

/**
 * Radix Dialog only returns focus to its own Dialog.Trigger. Dialogs opened by
 * a keyboard shortcut or an outside button remember the focused element when
 * they open and give focus back to it when they close.
 */
export function useReturnFocus() {
  const origin = useRef<HTMLElement | null>(null);
  return {
    onOpenAutoFocus: () => {
      const element = document.activeElement;
      origin.current =
        element instanceof HTMLElement && element !== document.body
          ? element
          : null;
    },
    onCloseAutoFocus: (event: Event, restore = true) => {
      event.preventDefault();
      const element = origin.current;
      origin.current = null;
      if (restore && element?.isConnected)
        element.focus({ preventScroll: true });
    },
  };
}
