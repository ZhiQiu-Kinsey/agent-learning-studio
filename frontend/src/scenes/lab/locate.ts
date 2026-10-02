import type { StudioState } from "../../hooks/useStudio";

/** Replays up to a recorded event and selects it in the inspector. */
export function locateEvent(
  studio: Pick<StudioState, "seek" | "selectEvent">,
  index: number,
) {
  studio.seek(index + 1);
  studio.selectEvent(index);
}
