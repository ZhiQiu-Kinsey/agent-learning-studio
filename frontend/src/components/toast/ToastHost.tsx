import { useEffect } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { CircleAlert, CircleCheck, Info } from "lucide-react";
import SwipeToast from "../react-bits/SwipeToast";
import { dismiss, useToasts, type ToastTone } from "./toast";

/** Newest stays at the bottom edge; older ones are dropped beyond this. */
const MAX_VISIBLE = 4;
const toneStyle: Record<
  ToastTone,
  { accent: string; duration: number; icon: typeof Info }
> = {
  success: { accent: "#6fd39a", duration: 5000, icon: CircleCheck },
  info: { accent: "#9d8fff", duration: 5000, icon: Info },
  // Failures stay longer so there is time to read the reason.
  error: { accent: "#ff9473", duration: 9000, icon: CircleAlert },
};

/**
 * Global notification host (React Bits SwipeToast feel): cards rise from the
 * bottom edge, swipe down or press Esc/the close button to dismiss, pause while
 * hovered or focused, and leave on their own once the fuse burns out.
 */
export function ToastHost() {
  const { t } = useTranslation("common");
  const toasts = useToasts();
  useEffect(() => {
    if (toasts.length > MAX_VISIBLE)
      toasts.slice(0, toasts.length - MAX_VISIBLE).forEach((toast) => {
        dismiss(toast.id);
      });
  }, [toasts]);
  return createPortal(
    <section
      className="toast-host"
      aria-label={t("toast.region")}
      data-testid="toast-host"
    >
      {toasts.slice(-MAX_VISIBLE).map((toast) => {
        const tone = toneStyle[toast.tone];
        const Icon = tone.icon;
        return (
          <SwipeToast
            key={toast.id}
            className={`toast-card is-${toast.tone}`}
            role={toast.tone === "error" ? "alert" : "status"}
            accent={tone.accent}
            duration={tone.duration}
            title={toast.title}
            description={toast.description}
            icon={<Icon size={18} strokeWidth={2.2} />}
            closeLabel={t("toast.close")}
            onClose={() => dismiss(toast.id)}
          />
        );
      })}
    </section>,
    document.body,
  );
}
