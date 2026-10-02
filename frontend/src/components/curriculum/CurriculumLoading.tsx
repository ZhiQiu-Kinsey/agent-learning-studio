import { useTranslation } from "react-i18next";
import { LoaderCircle } from "lucide-react";
import { Button } from "../ui/button";

/** Shown until `/api/curriculum` arrives; offers a retry when it failed. */
export function CurriculumLoading({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  const { t } = useTranslation("curriculum");
  return (
    <section className="panel curriculum-loading">
      <h1>{t("title")}</h1>
      {error ? (
        <div className="alert" role="alert">
          <span>{t("loadFailed", { reason: error })}</span>
          <Button className="text-button" onClick={onRetry}>
            {t("retry")}
          </Button>
        </div>
      ) : (
        <p role="status">
          <LoaderCircle size={18} className="spin" />
          {t("loading")}
        </p>
      )}
    </section>
  );
}
