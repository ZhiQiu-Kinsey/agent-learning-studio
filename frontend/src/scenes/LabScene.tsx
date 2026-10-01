import { Laboratory } from "../components/workspace/Laboratory";
import { LessonExtension } from "../lesson-extensions/LessonExtension";
import type { SceneProps } from "./types";

/** 实验：real runs drive the stage; lesson extensions may add inputs or lenses. */
export function LabScene({ studio, active, onConfigure }: SceneProps) {
  return (
    <div className="scene-lab" data-testid="scene-lab">
      <LessonExtension
        slot="lab"
        extensionKey={studio.detail?.ui?.lab}
        studio={studio}
        active={active}
        onConfigure={onConfigure}
      >
        <Laboratory studio={studio} active={active} onConfigure={onConfigure} />
      </LessonExtension>
    </div>
  );
}
