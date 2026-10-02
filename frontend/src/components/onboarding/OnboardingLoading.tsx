import { useTranslation } from "react-i18next";
import { Compass } from "lucide-react";
import { Button } from "../ui/button";

/** Shown until `/api/onboarding` arrives; offers a retry when it failed. */
export function OnboardingLoading({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  const { t } = useTranslation("curriculum", { keyPrefix: "onboarding" });
  return (
    <div className="onboarding-loading" role={error ? "alert" : "status"}>
      <Compass size={32} />
      <h1>{t("loadingTitle")}</h1>
      <p>{error ? t("loadFailed", { reason: error }) : t("loading")}</p>
      {error && (
        <Button data-testid="onboarding-retry" onClick={onRetry}>
          {t("retry")}
        </Button>
      )}
    </div>
  );
}
