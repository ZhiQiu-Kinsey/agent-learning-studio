// Collects the lesson recordings (lessons/*/recordings/*.json, see
// docs/architecture/event-envelope-v2.md section 6) into the site's replay index. The files
// are copied byte for byte; this only reads them. Full validation (integrity hash, envelope
// replay, secret scan, source hash) is scripts/validate_recordings.py, which the Pages
// workflow runs before building; the checks here only refuse what the site could not show.
import { digest } from "./curriculum.mjs";

const NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function exerciseTitle(manifest, overlays, exerciseId) {
  const exercise = manifest.exercises?.find((item) => item.id === exerciseId);
  if (!exercise) throw new Error(`exercise ${exerciseId} is not in lesson ${manifest.id}`);
  const title = { "zh-CN": exercise.title };
  for (const [locale, overlay] of Object.entries(overlays)) {
    const entry = overlay?.texts?.[`exercises.${exerciseId}.title`];
    title[locale] =
      entry && entry.source === digest(exercise.title) ? entry.text : null;
  }
  return title;
}

/** Counts read from the events as recorded; usage a response did not report stays unreported. */
export function recordingStats(events) {
  const responses = events.filter(
    (event) => event.type === "response" && event.data?.endpoint !== "embeddings",
  );
  const usages = responses.map((event) => event.data?.body?.usage?.total_tokens);
  const reported = usages.filter((value) => Number.isFinite(value));
  return {
    events: events.length,
    requests: events.filter((event) => event.type === "request").length,
    toolCalls: events.filter((event) => event.type === "tool_call").length,
    approvals: events.filter((event) => event.type === "approval_requested").length,
    // null when no response reported usage; `unreported` counts the responses without it.
    totalTokens: reported.length ? reported.reduce((sum, value) => sum + value, 0) : null,
    unreported: usages.length - reported.length,
  };
}

function check(condition, file, message) {
  if (!condition) throw new Error(`${file}: ${message}`);
}

/**
 * One recording file → its index entry. `file` is the repository-relative path, used only in
 * error messages; `lesson` is the lesson's manifest plus its overlays and catalog number.
 */
export function recordingEntry(file, name, document, lesson) {
  check(NAME.test(name), file, "recording names are kebab-case");
  const { metadata, events } = document ?? {};
  check(metadata && Array.isArray(events) && events.length > 0, file, "needs metadata and events");
  check(metadata.lesson === lesson.manifest.id, file, "metadata.lesson differs from the lesson folder");
  check(metadata.event_count === events.length, file, "event_count differs from the events");
  check(events[0].type === "run_start" && events.at(-1).type === "done", file,
    "a recording starts with run_start and ends with done");
  check(events.every((event) => event.provenance === "recorded_run"), file,
    "every event of a recording is recorded_run");
  check(events.every((event, index) => event.seq === index + 1), file, "seq runs from 1 without gaps");
  check(typeof metadata.locale === "string", file, "metadata.locale is missing");
  return {
    lesson: lesson.manifest.id,
    number: lesson.number,
    exercise: metadata.exercise_id,
    exerciseTitle: exerciseTitle(lesson.manifest, lesson.overlays, metadata.exercise_id),
    inspector: lesson.manifest.ui?.inspector ?? null,
    name,
    path: `data/recordings/${lesson.manifest.id}/${name}.json`,
    metadata: {
      model: metadata.model,
      provider_label: metadata.provider_label,
      representation: metadata.representation,
      sdk: metadata.sdk,
      recorded_at: metadata.recorded_at,
      locale: metadata.locale,
      status: metadata.status,
      platform_version: metadata.platform_version,
      run_id: metadata.run_id,
    },
    stats: recordingStats(events),
  };
}

/** Groups entries by lesson and exercise, in catalog order, one recording per run language. */
export function groupRecordings(entries) {
  const groups = new Map();
  for (const entry of entries) {
    const key = `${entry.lesson}/${entry.exercise}`;
    if (!groups.has(key))
      groups.set(key, {
        id: key.replace("/", "--"),
        lesson: entry.lesson,
        number: entry.number,
        exercise: entry.exercise,
        exerciseTitle: entry.exerciseTitle,
        inspector: entry.inspector,
        recordings: {},
      });
    const group = groups.get(key);
    const previous = group.recordings[entry.metadata.locale];
    // Two recordings of the same exercise and language: the newer run is shown.
    if (!previous || previous.metadata.recorded_at < entry.metadata.recorded_at)
      group.recordings[entry.metadata.locale] = entry;
  }
  return [...groups.values()].sort(
    (a, b) => a.number - b.number || a.exercise.localeCompare(b.exercise),
  );
}
