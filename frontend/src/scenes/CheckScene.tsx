import { useTranslation } from "react-i18next";
import { Quiz } from "../components/Quiz";
import { CheckpointBlock } from "../components/check/CheckpointBlock";
import { TraceHuntBlock } from "../components/check/TraceHuntBlock";
import { sceneBlocks } from "../content/view";
import { track } from "../progress";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";
import "../styles/self-check.css";

/**
 * 自检：按内容 scenes.check.blocks 的顺序渲染 自测 / 轨迹找错 / 检查点。
 * 得分、信心、找到的证据和勾选只写入本机进度，不判定“已掌握”。
 */
export function CheckScene({ studio, goTo }: SceneProps) {
  const { t } = useTranslation("lesson", { keyPrefix: "check" });
  const detail = studio.detail!;
  const blocks = sceneBlocks(detail.learning, "check");
  return (
    <div className="scene-check learning-experience" data-testid="scene-check">
      <div className="learn-tab-content check-blocks">
        {!blocks.length && <div className="quiz-empty">{t("empty")}</div>}
        {blocks.map((block) => {
          switch (block.type) {
            case "quiz":
              return (
                <Quiz
                  key={`${detail.id}-${block.id}`}
                  title={block.title}
                  questions={block.questions}
                  confidence={block.confidence}
                  onScored={(correct, total, answers) =>
                    track.quizScored(
                      detail.id,
                      block.id,
                      correct,
                      total,
                      answers,
                    )
                  }
                />
              );
            case "trace-hunt":
              return (
                <TraceHuntBlock
                  key={`${detail.id}-${block.id}`}
                  block={block}
                  lessonId={detail.id}
                  events={studio.events}
                  running={studio.running}
                  runId={studio.runId}
                  onOpenLab={() => goTo("lab")}
                />
              );
            case "checkpoint":
              return (
                <CheckpointBlock
                  key={`${detail.id}-${block.id}`}
                  block={block}
                  lessonId={detail.id}
                />
              );
            default:
              return null;
          }
        })}
      </div>
    </div>
  );
}
