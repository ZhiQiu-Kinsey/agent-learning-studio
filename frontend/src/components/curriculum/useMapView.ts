import { useState } from "react";

export const mapViews = ["domains", "roadmap", "list"] as const;
export type MapView = (typeof mapViews)[number];
const viewStorageKey = "agent-lab-map-view";

function readView(): MapView {
  try {
    const saved = sessionStorage.getItem(viewStorageKey);
    return mapViews.includes(saved as MapView) ? (saved as MapView) : "domains";
  } catch {
    return "domains";
  }
}

/** The chosen map view, kept for this browser session. */
export function useMapView() {
  const [view, setViewState] = useState<MapView>(readView);
  const setView = (value: string) => {
    if (!mapViews.includes(value as MapView)) return;
    setViewState(value as MapView);
    try {
      sessionStorage.setItem(viewStorageKey, value);
    } catch {
      /* The choice still applies to this visit. */
    }
  };
  return [view, setView] as const;
}
