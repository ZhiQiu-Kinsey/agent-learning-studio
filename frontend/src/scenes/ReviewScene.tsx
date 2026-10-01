import { useTranslation } from "react-i18next";
import { useProgress } from "../progress";
import type { SceneProps } from "./types";

/** 回顾：only what really happened on this device; never claims mastery. */
export function ReviewScene({ studio }: SceneProps) {
  const { t } = useTranslation("lesson", { keyPrefix: "review" });
  const detail = studio.detail!;
  const record = useProgress().lessons[detail.id];
  return (
    <section
      className="scene-review"
      data-testid="scene-review"
      aria-label={t("title")}
    >
      <h2>{t("title")}</h2>
      <p>{t("help")}</p>
      {!record && <p>{t("empty")}</p>}
    </section>
  );
}
