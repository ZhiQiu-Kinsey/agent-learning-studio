import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../../components/ui/dialog";
import { useReturnFocus } from "../../components/command/returnFocus";
import { labShortcutList } from "./shortcuts";
import "../../styles/command.css";

/** `?` overlay listing every lab shortcut; Radix traps focus and handles Esc; focus returns to where ? was pressed. */
export function ShortcutHelp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation("command", { keyPrefix: "shortcuts" });
  const focus = useReturnFocus();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="shortcut-help"
        data-testid="shortcut-help"
        showCloseButton={false}
        // Esc closes only this overlay, not the guide bar listening on window.
        onEscapeKeyDown={(event) => event.stopPropagation()}
        onOpenAutoFocus={focus.onOpenAutoFocus}
        onCloseAutoFocus={(event) => focus.onCloseAutoFocus(event)}
      >
        <DialogClose asChild>
          <Button
            variant="ghost"
            size="icon"
            className="shortcut-close"
            aria-label={t("close")}
            data-testid="shortcut-help-close"
          >
            <X size={16} aria-hidden="true" />
          </Button>
        </DialogClose>
        <DialogTitle>{t("title")}</DialogTitle>
        <DialogDescription>{t("description")}</DialogDescription>
        <table className="shortcut-table">
          <thead>
            <tr>
              <th scope="col">{t("keys")}</th>
              <th scope="col">{t("action")}</th>
            </tr>
          </thead>
          <tbody>
            {labShortcutList.map(({ id, keys }) => (
              <tr key={id} data-testid={`shortcut-row-${id}`}>
                <td>
                  {keys.map((key) => (
                    <kbd key={key}>{key === "Space" ? t("space") : key}</kbd>
                  ))}
                </td>
                <td>{t(`items.${id}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="shortcut-note">{t("guide")}</p>
      </DialogContent>
    </Dialog>
  );
}
