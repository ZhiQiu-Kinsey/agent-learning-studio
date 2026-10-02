import { useTranslation } from "react-i18next";
import { BookOpen, CircleCheck, Play } from "lucide-react";
import type { LessonMarks } from "./graph";

/** Icons for what this browser recorded; each mark is labelled for screen readers. */
export function ProgressMarks({
  marks,
  testId,
}: {
  marks: LessonMarks;
  testId: string;
}) {
  const { t } = useTranslation("curriculum");
  const items = [
    { key: "opened", on: marks.opened, Icon: BookOpen, label: t("marks.opened") },
    { key: "ran", on: marks.ran, Icon: Play, label: t("marks.ran") },
    { key: "quizzed", on: marks.quizzed, Icon: CircleCheck, label: t("marks.quizzed") },
  ].filter((item) => item.on);
  return (
    <span
      className="curriculum-marks"
      data-testid={testId}
      data-opened={marks.opened}
      data-ran={marks.ran}
      data-quizzed={marks.quizzed}
    >
      <span className="sr-only">{t("marks.label")} </span>
      {items.length ? (
        items.map(({ key, Icon, label }) => (
          <span key={key} className="curriculum-mark" data-mark={key} title={label}>
            <Icon size={12} aria-hidden="true" />
            <span className="sr-only">{label}</span>
          </span>
        ))
      ) : (
        <span className="sr-only">{t("marks.none")}</span>
      )}
    </span>
  );
}
