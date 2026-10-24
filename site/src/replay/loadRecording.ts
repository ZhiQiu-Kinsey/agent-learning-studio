import type { Trace } from "@studio/types";

export class RecordingLoadError extends Error {}

/**
 * Reads one published recording file. Only a document that looks like a recorded run
 * is accepted: the site shows recordings, never anything else as run evidence.
 */
export function parseRecording(document: unknown): Trace[] {
  const value = document as { metadata?: unknown; events?: unknown } | null;
  const events = value?.events;
  if (!value?.metadata || !Array.isArray(events) || !events.length)
    throw new RecordingLoadError("not a recording");
  events.forEach((event: Trace, index) => {
    if (event?.provenance !== "recorded_run")
      throw new RecordingLoadError(`event ${index + 1} is not recorded_run`);
    if (event.seq !== index + 1)
      throw new RecordingLoadError(`event ${index + 1} has seq ${event.seq}`);
  });
  if (events[0].type !== "run_start" || events.at(-1).type !== "done")
    throw new RecordingLoadError("a recording starts with run_start and ends with done");
  return events as Trace[];
}

export async function loadRecording(
  path: string,
  { base = import.meta.env.BASE_URL, signal, fetcher = fetch }: {
    base?: string;
    signal?: AbortSignal;
    fetcher?: typeof fetch;
  } = {},
) {
  const response = await fetcher(`${base}${path}`, { signal });
  if (!response.ok) throw new RecordingLoadError(`HTTP ${response.status}`);
  return parseRecording(await response.json());
}
