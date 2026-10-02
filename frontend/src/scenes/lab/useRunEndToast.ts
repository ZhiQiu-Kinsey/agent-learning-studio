import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { StudioState } from "../../hooks/useStudio";
import { notify } from "../../components/toast/toast";

/** Reports how a live run really ended, once, when it stops running. */
export function useRunEndToast(studio: StudioState) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "toast" });
  const wasRunning = useRef(false);
  useEffect(() => {
    const ended = wasRunning.current && !studio.running;
    wasRunning.current = studio.running;
    if (!ended) return;
    const events = studio.events;
    const last = events.at(-1);
    const error = events.findLast((event) => event.type === "error");
    if (last?.type === "done" && last.data.status === "completed") {
      const ms = Date.parse(last.timestamp) - Date.parse(events[0].timestamp);
      notify({
        tone: "success",
        title: t("completed"),
        description: Number.isFinite(ms)
          ? t("completedDetail", {
              count: events.length,
              seconds: new Intl.NumberFormat(i18n.language, {
                maximumFractionDigits: 2,
              }).format(Math.max(0, ms) / 1000),
            })
          : t("completedCount", { count: events.length }),
      });
    } else if (error) {
      notify({
        tone: "error",
        title: t("error"),
        description:
          typeof error.data.message === "string" && error.data.message
            ? error.data.message
            : t("errorFallback"),
      });
    }
    // Only the running edge matters; events are read at that moment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studio.running]);
}
