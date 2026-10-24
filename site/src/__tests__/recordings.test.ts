import fs from "node:fs";
import { describe, expect, it } from "vitest";
import { groupRecordings, recordingEntry, recordingStats } from "../../scripts/lib/recordings.mjs";
import index from "../generated/recordings.json";
import { loadRecording, parseRecording, RecordingLoadError } from "../replay/loadRecording";

const root = new URL("../../../", import.meta.url);
const site = new URL("../../", import.meta.url);
const read = (url: URL) => JSON.parse(fs.readFileSync(url, "utf8"));

type Group = (typeof index)[number];
const entries = (index as Group[]).flatMap((group) => Object.values(group.recordings));

describe("replay index", () => {
  it("has a recording per published file, each one a real recorded run", () => {
    expect(entries.length).toBeGreaterThan(0);
    for (const entry of entries) {
      const document = read(new URL(`public/${entry.path}`, site));
      expect(entry.metadata.run_id).toBe(document.metadata.run_id);
      expect(entry.metadata.model).toBe(document.metadata.model);
      expect(parseRecording(document)).toHaveLength(document.metadata.event_count);
      expect(entry.stats).toEqual(recordingStats(document.events));
    }
  });

  it("copies the lesson recordings byte for byte", () => {
    for (const entry of entries) {
      const published = fs.readFileSync(new URL(`public/${entry.path}`, site));
      const folder = fs
        .readdirSync(new URL("lessons/", root))
        .find((name) =>
          fs.existsSync(new URL(`lessons/${name}/recordings/${entry.name}.json`, root)) &&
          read(new URL(`lessons/${name}/lesson.json`, root)).id === entry.lesson,
        );
      expect(folder).toBeDefined();
      const source = fs.readFileSync(new URL(`lessons/${folder}/recordings/${entry.name}.json`, root));
      expect(published.equals(source)).toBe(true);
    }
  });

  it("counts tokens only when the provider reported them", () => {
    const events = [
      { type: "response", data: { body: { usage: { total_tokens: 10 } } } },
      { type: "response", data: { body: {} } },
    ];
    expect(recordingStats(events)).toMatchObject({ totalTokens: 10, unreported: 1 });
    expect(recordingStats([{ type: "response", data: { body: {} } }])).toMatchObject({
      totalTokens: null,
      unreported: 1,
    });
  });

  it("groups one recording per run language and refuses events that are not recorded", () => {
    const [entry] = entries;
    const document = read(new URL(`public/${entry.path}`, site));
    const lesson = { manifest: { id: entry.lesson, exercises: [{ id: entry.exercise, title: "t" }] }, overlays: {}, number: 1 };
    const built = recordingEntry("x.json", entry.name, document, lesson);
    const [group] = groupRecordings([built]);
    expect(group.recordings[document.metadata.locale].name).toBe(entry.name);
    const tampered = structuredClone(document);
    tampered.events[1].provenance = "real_run";
    expect(() => recordingEntry("x.json", entry.name, tampered, lesson)).toThrow(/recorded_run/);
  });
});

describe("loading a recording", () => {
  const [entry] = entries;
  const document = read(new URL(`public/${entry.path}`, site));

  it("reads the published file under the base path", async () => {
    const seen: string[] = [];
    const fetcher = (async (url: string) => {
      seen.push(url);
      return new Response(JSON.stringify(document));
    }) as unknown as typeof fetch;
    const events = await loadRecording(entry.path, { base: "/agent-learning-studio/", fetcher });
    expect(seen).toEqual([`/agent-learning-studio/${entry.path}`]);
    expect(events.map((event) => event.seq)).toEqual(document.events.map((_: unknown, i: number) => i + 1));
  });

  it("rejects a document that is not a recorded run", () => {
    const live = structuredClone(document);
    live.events[0].provenance = "real_run";
    expect(() => parseRecording(live)).toThrow(RecordingLoadError);
    const gap = structuredClone(document);
    gap.events.splice(1, 1);
    expect(() => parseRecording(gap)).toThrow(/seq/);
    expect(() => parseRecording({ events: [] })).toThrow(RecordingLoadError);
  });

  it("reports an HTTP failure", async () => {
    const fetcher = (async () => new Response("", { status: 404 })) as unknown as typeof fetch;
    await expect(loadRecording(entry.path, { base: "/", fetcher })).rejects.toThrow(/404/);
  });
});
