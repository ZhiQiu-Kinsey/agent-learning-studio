import { Quiz } from "../components/Quiz";
import { lessonView } from "../content/view";
import { track } from "../progress";
import type { SceneProps } from "./types";
import "../styles/learning-experience.css";

/** 自检：self-check questions with explanations; scores are recorded locally only. */
export function CheckScene({ studio }: SceneProps) {
  const detail = studio.detail!;
  return (
    <div className="scene-check learning-experience" data-testid="scene-check">
      <div className="learn-tab-content">
        <Quiz
          key={detail.id}
          questions={lessonView(detail.learning).quiz}
          onScored={(correct, total) =>
            track.quizScored(detail.id, correct, total)
          }
        />
      </div>
    </div>
  );
}
