import { useEffect, useState } from "react";

/**
 * Real elapsed milliseconds since a server timestamp, ticking while `startAt`
 * is set. Nothing is estimated: when the timestamp is missing or unreadable the
 * result is null and callers show no number.
 */
export function useElapsedMs(startAt: string | null | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!startAt) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [startAt]);
  if (!startAt) return null;
  const start = Date.parse(startAt);
  return Number.isFinite(start) ? Math.max(0, now - start) : null;
}
