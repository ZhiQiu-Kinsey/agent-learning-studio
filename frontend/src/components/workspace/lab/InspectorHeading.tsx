import { useTranslation } from "react-i18next";
import { Waypoints } from "lucide-react";
import type { StudioState } from "../../../hooks/useStudio";
import type { Trace } from "../../../types";
import StatusMark from "../../react-bits/StatusMark";
import { pendingApproval } from "./approvals";

/** Title of the run observatory and the real status of the current run. */
export function InspectorHeading({
  studio: s,
  active,
  completed,
  last,
}: {
  studio: StudioState;
  active: boolean;
  completed: boolean;
  last: Trace | undefined;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "bench" });
  return (
    <div className="inspector-heading">
      <div>
        <h2>
          <Waypoints size={18} />
          {t("inspector.title")}
        </h2>
        <p>{t("inspector.subtitle")}</p>
      </div>
      <span
        className={`trace-status ${s.running ? "is-running" : ""}`}
        data-testid="lab-trace-status"
      >
        <span aria-hidden="true">
          <StatusMark
            size={16}
            strike={false}
            status={
              s.running && active
                ? "running"
                : completed
                  ? "done"
                  : s.events.some((e) => e.type === "error")
                    ? "failed"
                    : last?.data.status === "cancelled"
                      ? "cancelled"
                      : "pending"
            }
            doneColor="var(--success)"
            errorColor="var(--danger)"
          />
        </span>
        {s.running
          ? s.stopping
            ? t("status.stopping")
            : pendingApproval(s.events)
              ? t("status.awaitingApproval")
              : t("status.running")
          : completed
            ? t("status.completed")
            : s.events.length
              ? t("status.ended")
              : t("status.idle")}
      </span>
    </div>
  );
}
