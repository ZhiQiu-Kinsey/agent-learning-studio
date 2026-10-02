import { useTranslation } from "react-i18next";
import { FlaskConical } from "lucide-react";
import type { Evidence } from "./useEvidence";

/** Opens a tool's latest real result in 实验; explains when there is none. */
export function EvidenceButton({
  name,
  at,
  evidence,
  onOpen,
}: {
  name: string;
  at: string;
  evidence: Evidence | null;
  onOpen: (name: string, at: string) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code.evidence" });
  const shown = evidence?.at === at ? evidence : null;
  return (
    <div className="code-evidence">
      <button
        type="button"
        data-testid="code-evidence"
        data-tool={name}
        aria-label={t("label", { name })}
        onClick={() => onOpen(name, at)}
      >
        <FlaskConical size={14} aria-hidden="true" />
        <code>{name}</code>
        <span>{t("open")}</span>
      </button>
      {shown && (
        <p role="status" data-testid="code-evidence-status">
          {t(shown.reason, { name })}
        </p>
      )}
    </div>
  );
}
