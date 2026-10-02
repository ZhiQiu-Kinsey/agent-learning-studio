import { Check, CheckCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Checkpoint } from "../../content/types.gen";
import { track, useProgress } from "../../progress";

/** 自检里检查点的进度键：块 id 加条目 id，避免不同块的条目 id 相撞。 */
export const checkpointKey = (blockId: string, itemId: string) =>
  `${blockId}/${itemId}`;

/** 学习者自报的检查点：只记录勾选，保存在本机，不计分、不判定掌握。 */
export function CheckpointBlock({
  block,
  lessonId,
}: {
  block: Checkpoint;
  lessonId: string;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "check.checkpoint" });
  const checked = useProgress().lessons[lessonId]?.checkpoints ?? {};
  return (
    <section
      className="check-block checkpoint-block"
      data-testid="checkpoint-block"
      data-block-id={block.id}
      aria-labelledby={`${block.id}-title`}
    >
      <div className="check-eyebrow">
        <CheckCheck size={14} aria-hidden="true" />
        {t("eyebrow")}
      </div>
      <h3 id={`${block.id}-title`}>{block.title}</h3>
      {block.prompt && <p>{block.prompt}</p>}
      <div className="checkpoint-items">
        {block.items.map((item) => {
          const id = checkpointKey(block.id, item.id);
          return (
            <label key={id} data-testid="checkpoint-item">
              <input
                type="checkbox"
                checked={!!checked[id]}
                onChange={(event) =>
                  track.checkpointSet(lessonId, id, event.target.checked)
                }
              />
              <span className="checkpoint-icon" aria-hidden="true">
                {checked[id] && <Check size={13} />}
              </span>
              <span>{item.text}</span>
            </label>
          );
        })}
      </div>
      <small>{t("note")}</small>
    </section>
  );
}
