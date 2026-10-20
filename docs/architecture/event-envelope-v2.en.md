# Event envelope v2 and run storage

**English** · [简体中文](event-envelope-v2.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

Confirmed on 2026-10-01. This corresponds to subtask 3 of phase 1 in the [redesign plan](redesign-plan.md). The constraints come from sections 6.1, 6.3 and 6.5 and decisions 4 and 5 of the [curriculum research](curriculum-research.md).

## 1. A run is a server-side resource

| Endpoint | Purpose | Main error codes |
| --- | --- | --- |
| `POST /api/runs` | The request body is the same as the old `/api/run` (`lesson_id`, `mode`, `question`, `exercise_id`, `inputs`). After validation, the run starts in the background and the endpoint returns `202 {run_id}` | `409 run_busy` (execution mutex) |
| `GET /api/runs/{id}/events?from_seq=N` | SSE: first replays the stored events with `seq ≥ N`, then continues with live events, and ends after `done`. Also accepts the `Last-Event-ID` header | `404 run_not_found` |
| `GET /api/runs?limit=` | List of runs (newest first), metadata only | |
| `GET /api/runs/{id}` | Metadata of one run, including `event_count` and `last_seq` | `404 run_not_found` |
| `DELETE /api/runs` | Clear all records in one step | `409 run_active` |
| `POST /api/runs/{id}/cancel` | Stop the later steps of the given run | `409 run_not_active`, `404` |
| `POST /api/runs/{id}/approvals` | Approval skeleton. Request body `{approval_id, decision: approve\|reject, note?}` | `409 no_pending_approval`, `404 run_not_found` |

An error response is `{"detail": "中文说明", "code": "稳定错误码"}`, that is, a human-readable `detail` message plus a stable machine-readable `code`. `detail` is the same as in the old endpoint, and the frontend displays it as before.

The old `POST /api/run` has been removed. The frontend, the Python tests, the browser tests and `scripts/verify_providers_live.py` all moved to the new endpoints. Keeping two execution paths would leave two semantics side by side: "disconnect cancels the run" and "disconnect can be resumed".

### Stop and disconnect

- A dropped event-reading connection does **not** cancel the run. After reconnecting, the reader resumes from `from_seq`.
- When the user clicks "Stop run" or the page closes (`pagehide`, a `keepalive` request), the frontend calls `cancel`. This keeps the earlier behavior that closing the page stops the later steps. A model request that has already been sent is still bound by the 60-second network timeout.
- When a run ends, the server first writes `done` and the run status to storage and releases the execution mutex, and only then publishes `done` to readers. A client that receives `done` can start the next run right away.

### How resuming avoids duplicates and gaps

Within one run, `seq` increases consecutively from 1, and storage uses `(run_id, seq)` as the primary key. While a run is in progress, only committed events are published to readers (the `published` watermark). A reader that disconnects reconnects with `from_seq = last received seq + 1`, the server replays from storage, and the frontend then drops events with `seq ≤ the last one already received`. It reports a failure only after 5 consecutive retries bring no new event.

## 2. Envelope fields

The v1 fields `schema_version`, `type`, `round`, `timestamp` and `data` stay. `schema_version` becomes `2`, and these fields are new:

| Field | Description |
| --- | --- |
| `run_id` | Run ID, 32 hexadecimal characters |
| `seq` | Increases monotonically from 1 within one run |
| `span_id` / `parent_span_id` / `span_kind` | The span the event belongs to and its parent. `span_kind` is one of `run`, `agent`, `step`, `llm`, `tool` |
| `actor` / `role` | Default `"agent"` / `null`. Reserved for multi-agent runs and roles such as planner and reviewer |
| `provenance` | `real_run`, `recorded_run`, `offline_recompute`, `illustration`. Every run on this platform writes `real_run` |
| `representation` | Has a value only on `request` / `response`; `null` on all other events |
| `sdk` | Has a value only when `representation = sdk_standardized`: `{name, version}` |

The server fills in every envelope field. Lesson code can emit only `type/round/data`, so it cannot declare its own provenance or representation level.

### How `representation` is determined

| Run path | `representation` | `sdk` |
| --- | --- | --- |
| Bailian raw HTTP (`course/api_client.send_bailian`; the request body is the JSON that urllib sends) | `http_body` | `null` |
| LiteLLM multi-provider (`course/providers.SDKCompletion`; the input is SDK parameters and the output is `model_dump()`) | `sdk_standardized` | `{"name": "litellm", "version": installed version}` |
| Bailian embeddings (`course/api_client.send_bailian_embeddings`; `/embeddings` of the same workspace) | `http_body` | `null` |
| LiteLLM embeddings (`course/providers.SDKEmbedding`; `model_dump()` of `litellm.embedding`) | `sdk_standardized` | `{"name": "litellm", "version": installed version}` |
| Deterministic test adapter (automated tests only) | `sdk_standardized` | `{"name": "deterministic-test-adapter", "version": null}` |
| Local lessons that don't call a model | `null` | `null` |

Embedding requests use the same connection as the run's chat requests, so they carry the same representation; nothing is labeled separately.

### Embedding requests

A lesson sends an embedding request with `context.embed(texts, round_number=1, *, branch=None, dimensions=None)`. It is still a `request` / `response` pair that opens and closes an `llm` span, with one more field in `data`: `endpoint: "embeddings"`. A request without `endpoint` is a chat completion:

```json
{"type": "request", "data": {"endpoint": "embeddings", "representation": "http_body",
  "body": {"model": "text-embedding-v4", "input": ["chunk one", "chunk two"], "dimensions": 256}}}
{"type": "response", "data": {"endpoint": "embeddings", "representation": "http_body", "duration_ms": 412,
  "body": {"data": [{"index": 0, "embedding": [0.012, "..."]}, {"index": 1, "embedding": ["..."]}],
           "model": "text-embedding-v4", "usage": {"prompt_tokens": 9, "total_tokens": 9}}}}
```

- `body` is recorded as it is: the request body is the JSON that was sent (without `dimensions` when the lesson passed none; the platform never fills in the provider's default), and the response body is the provider's full JSON or the SDK's `model_dump()`. Vectors are stored in full in the run store and in recordings. Only the UI truncates them for display, and says so.
- With a `branch`, the pair is matched by `branch`, like parallel chat requests.
- Embedding requests count toward `max_model_calls` (the lesson's `runtime.max_rounds`); chat and embedding requests share one budget.
- One request carries at most `context.embedding_batch_limit` inputs (10 on Bailian's compatible endpoint); lesson code splits larger sets itself. Going over the limit, an empty list or an empty string is a programming error (`ValueError`) and sends no event. When the response has a different number of vectors than inputs, the response is recorded first and then the run stops.
- When the exercise uses embeddings (`lesson.json` declares `testing.embedding_factory`, or the exercise says `requires_embedding: true`), `run_start.data.embedding_model` records the run's embedding model.

Red line: SDK-standardized data is never labeled `http_body` or `wire`. `EnvelopeBuilder` rejects `sdk_standardized` without SDK information, and it also rejects SDK information attached to non-SDK data. No path currently produces `wire` or `parsed`. The v1 field `data.representation` stays as before.

## 3. Span rules

The constant table is declared once, as `SPAN_EVENTS` in `server/envelope.py`. `scripts/export_trace_contract.py` generates the frontend mirror `frontend/src/generated/trace-contract.ts`, and `tests/test_runs.py` checks that the two match. After you change the constant table, run:

```powershell
.\.venv\Scripts\python.exe scripts/export_trace_contract.py
```

| Event | Phase | Span |
| --- | --- | --- |
| `run_start` → `done` | start / end | `run` root span, `parent_span_id = null` |
| `request` → `response` | start / end; parallel branches are paired by `data.branch` | `llm` |
| `tool_call` → `tool_result` | start / end, paired by `id` ↔ `tool_call_id` | `tool` |
| `answer`, `error`, `lesson.*` and other undeclared types | instant | attached to the current span |

- **step**: has no event of its own. Events with the same `round` belong to the same step span. A change of `round` starts a new step, whose parent is the run. The `agent` level is reserved for multi-agent lessons; a single-agent run doesn't generate it today.
- The parent of an `llm` or `tool` span is the current step. If the event has no `round`, the parent is the run.
- A `response` with a `branch` closes the `llm` span of the same `branch`. Without a `branch`, it closes the most recent unclosed `llm` span (a lesson starts parallel requests with `context.complete(..., branch=...)`). A `tool_result` closes the `tool` span with the same `id`. If there is no span to close, the event is treated as an instant event; the platform never invents a pairing.
- An instant event attaches to the innermost unclosed `llm` or `tool` span. If there is none, it attaches to the step of its `round`, or to the run when it has no `round`.
- When a new step starts or the run ends, an `llm` or `tool` span that is still unclosed stays unclosed. That means "no result" (for example, the run was stopped), and the platform doesn't fabricate an end event.
- For a start or end event, `span_id` is the span it opens or closes. For an instant event, `span_id` is the span it sits in. Span IDs look like `run-1`, `step-2`, `llm-3`, `tool-1` and are unique only within one run.

## 4. Run storage

- File: `.runtime/runs.sqlite3` (already in `.gitignore`). It is opened only when the first run is created. WAL mode, `synchronous=FULL`, `secure_delete=ON`.
- Tables: `runs` (`run_id`, `lesson_id`, `exercise_id`, `mode`, `model`, `provider_id`, `representation`, `provenance`, `schema_version`, `status`, `created_at`, `finished_at`, `locale`) and `events` (`run_id`, `seq`, `type`, `event`), with `(run_id, seq)` as the primary key. `locale` is the run language. A database created before this column existed gets it added when opened; all older runs are Chinese runs and are recorded as `zh-CN`.
- Append-only: each event is committed right after it is written, and a trigger on `events` rejects `UPDATE`. `done` and the run status are committed in the same transaction. The only delete path is the clear-all action, and the WAL is truncated afterwards.
- Only scrubbed events are stored: `scrub()` runs on `data` first, and the result is then serialized into the database. Envelope fields are generated by the platform and contain no user input. The event text in storage is the text that SSE sends.
- Status: `running`, `completed`, `error`, `cancelled`. At service start, any leftover `running` is marked `interrupted`. Such a run has no `done`, and a reader ends when it reaches the last event.
- Automated tests use `tests/run_support.py` to point storage at a temporary directory and never write to the real `.runtime/`.

## 5. Compatibility

- The event types `run_start/request/response/tool_call/tool_result/answer/error/done` and the `lesson.*` names, as well as the content of `data`, are unchanged.
- `request` / `response` may carry `data.endpoint: "embeddings"` (see "Embedding requests" in section 2); older records without the field are chat requests. `run_start.data.embedding_model` appears only when the exercise uses embeddings.
- `error.data` may carry a stable `code` (and optional `params`); the UI translates the code and says what to configure. The only one so far is `embedding_model_missing` (the selected provider has no embedding model; `params.setting` names the setting to change). `message` is still recorded in the run language.
- `run_start.data.locale` records the run language (`zh-CN`, `en`). When the language requested by the UI isn't supported by the lesson and the run falls back to the source language, `requested_locale` is recorded as well. An older run without `locale` is a Chinese run. The run language decides the language of all text in the events. Replay shows the record as it was; when the UI language differs, it only adds a label and doesn't translate.
- The frontend `Trace` type accepts both v1 and v2 and reads v2 fields as optional. `isTraceV2()` decides whether spans can be derived. A v1 record can only be read in array order.
- A downloaded run record gains `run_id`, and its events are v2. There is no import feature yet; when one is added, v1 records will be read by the rules above.
- Lesson recordings (`recorded_run`) are covered in section 6. Approval events (`approval.requested/resolved`) and the hash chain will be implemented in later subtasks.

## 6. Lesson recordings (`recorded_run`)

This corresponds to subtask 4 of phase 1 in the [redesign plan](redesign-plan.md) and decision 5 of the [curriculum research](curriculum-research.md). Implementation: `server/recordings.py`. Scripts: `scripts/export_recording.py` and `scripts/validate_recordings.py` (the latter is wired into `scripts/validate_lessons.py`).

### 6.1 Files and format

A recording is one JSON file: `lessons/<lesson directory>/recordings/<name>.json`, where `name` is kebab-case (lowercase letters, digits and hyphens, at most 64 characters). The file has exactly two keys:

```text
{ "metadata": { ... }, "events": [ envelope v2 events ... ] }
```

| Metadata field | Description |
| --- | --- |
| `schema_version` | Recording format version, currently `2` (the envelope version of the events is also `2`). From version 2 on, the metadata carries `locale` |
| `lesson` | Lesson slug. It must match the `lesson.json` in the lesson directory |
| `exercise_id` | Exercise ID. It must exist in the current lesson |
| `run_id` | Run ID of the source run, the same as `run_id` in the events |
| `status` | `completed` or `error` (a failed run is recorded as `error` in run storage). It must match `done.data.status` |
| `model`, `provider_id`, `provider_label` | Taken from the run record and the `run_start` event. They must match `run_start.data` |
| `representation` | `http_body` or `sdk_standardized` |
| `sdk` | `null` for `http_body`. For `sdk_standardized` it must be `{name, version}`, both non-empty strings |
| `recorded_at` | Start time of this real run (`created_at` of the run record, ISO 8601, UTC) |
| `platform_version` | Platform version at export time; how it is obtained is described below |
| `source_hash` | Hash of the lesson source; rules in 6.2 |
| `integrity_hash` | Event integrity hash; rules in 6.2 |
| `event_count` | Number of events |
| `locale` | Run language, taken from the run record. It must match `run_start.data.locale` and be one of the lesson's `runtime.locales` |

**How `platform_version` is obtained**: the `project.version` from `pyproject.toml` plus the git commit, in the form `0.1.0+g<12-character commit>`. If tracked files have uncommitted changes (`git status --porcelain --untracked-files=no` is non-empty), `.dirty` is appended. Without git, only the pyproject version is written. If no version can be read, it is `unknown`. It is for traceability only and takes no part in validation; whether the recording matches the source is decided by `source_hash`.

### 6.2 Hash rules

Both hashes are written as `sha256:<64 lowercase hexadecimal characters>`.

- **integrity_hash**: the sha256 of the canonical JSON of the `events` array. Canonical JSON means the UTF-8 bytes of `json.dumps(events, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`: keys sorted, no extra whitespace, non-ASCII characters kept as they are, and NaN/Infinity not allowed.
- **source_hash**: the files that take part, in order:
  1. `lessons/<lesson directory>/lesson.json`;
  2. all files listed in `sources` of `lesson.json`, de-duplicated and sorted lexicographically by relative path (POSIX separators).

  For each file, first normalize CRLF to LF in the bytes, then compute the sha256, and produce one line `<hex>  <relative path>\n` (the same format as `sha256sum` output). Concatenate the lines in the order above and compute the sha256 of the UTF-8 bytes of the result. Teaching text such as `content.json` takes no part in the hash, because it doesn't affect run results.

### 6.3 Export

```powershell
.\.venv\Scripts\python.exe scripts/export_recording.py --run <run_id> --name <name> [--replace]
```

The script opens `.runtime/runs.sqlite3` read-only and doesn't go through `RunStore`, so it never marks a run in progress as interrupted. It refuses to export in these cases:

- `mode` is not `live`, for example an offline deterministic test run;
- the status is not `completed` / `error`, including `cancelled`, `interrupted` and a `running` run that is still in progress;
- the provenance of the run or of any event is not `real_run`;
- the run has no model request or response (`representation` is empty), for example a local Python lesson. It can't be proven that such a run came from a real model;
- a lesson source file (the files in 6.2) was modified after this run started. The recording can't correspond to the source as it was at run time, so the run must be repeated;
- a recording with the same name exists and `--replace` was not given.

Events change in one place only: the top-level `provenance` goes from `real_run` to `recorded_run`. Every other field and the order stay exactly as they were; nothing is edited, trimmed or spliced. `sdk` comes from the first model request or response in the events. Before writing the file, the script runs two checks, and the file isn't written if either fails:

1. **Safety check**: reports every suspicious location (as a JSON path) without echoing the suspicious value.
2. **Full validation**: the same as 6.4, which guarantees that an exported file passes validation.

**Scope of the safety check** (every string and field name in the metadata and the events is checked):

- A string equal to any currently configured API key. Only keys of length ≥ 8 are compared. The script can see only keys from environment variables and local configuration; a key entered temporarily in the web page was already replaced by `scrub()` when it was written to storage.
- Common key formats: the `sk-` prefix, `AIza`, GitHub tokens such as `ghp_`, `xox?-`, `AKIA`, and `Bearer <token>`. `[REDACTED]` doesn't count.
- Authentication fields: a field named `authorization`, `proxy-authorization`, `api_key`, `apikey`, `x-api-key`, `api_secret`, `secret_key`, `access_token` or `client_secret` with a non-empty value. The comparison ignores case, `-` and `_`.
- Private local paths: Windows paths of a drive letter plus `Users` or `Documents and Settings`, `/Users/<name>`, `/home/<name>`, and the absolute paths of the local user's home directory and of the project directory (both separator styles, case-insensitive).

### 6.4 Validation

Both `scripts/validate_recordings.py` and `scripts/validate_lessons.py` scan all files under `lessons/*/recordings/`. If any check fails, the script exits with code 1 and reports the file and location.

1. The file name must be a kebab-case `.json`, and its directory must have a lesson implementation declaration.
2. The safety check is the same as in 6.3.
3. The metadata fields are complete and have the right types, `lesson` matches the lesson it sits in, and `event_count` matches the number of events.
4. `integrity_hash` matches the recomputed value.
5. The representation level matches the provider:
   - Bailian raw HTTP (`bailian`) can only be `http_body`, with `sdk = null`;
   - other providers go through LiteLLM, so they must be `sdk_standardized` with an SDK name and version;
   - `testing`, `local` and the deterministic test adapter are always rejected.

   So SDK data can't become `http_body` however it is relabeled.
6. **Envelope v2 replay**: use `EnvelopeBuilder(run_id, provenance="recorded_run", representation, sdk)` to regenerate the envelope for each event from its `type/data/round/timestamp`. The result must equal the recording exactly. This one check also covers the following, so the span rules aren't written out a second time:
   - `seq` increases consecutively from 1;
   - spans open and close correctly and have the right parents;
   - `actor` and `role`;
   - every event is `recorded_run`;
   - only model requests and responses carry `representation` and `sdk`.

   In addition: the `data.representation` (v1 field) of model events matches the metadata; the first event is the only `run_start` and the last is the only `done`; there is at least one model request; and in `run_start.data`, `mode` is `live` and `lesson_id`, `model`, `provider_id`, `provider_label`, `trace_representation` and `locale` match the metadata.
7. `source_hash` matches the current source. If it doesn't, the report says the source has changed and the recording must be redone. The platform doesn't silently keep using it.

### 6.5 Read-only endpoints

A recording is a lesson resource. It isn't written to run storage, doesn't appear in `/api/runs`, and can't be shown as "your run". `{id}` accepts a slug or an alias, and the response always returns the slug.

| Endpoint | Purpose | Main error codes |
| --- | --- | --- |
| `GET /api/lessons/{id}/recordings` | `{lesson_id, recordings: [{name, valid, error_code, metadata}]}`, without events. A recording whose source is out of date returns `valid=false, error_code="recording_stale"` with its metadata. For a recording that fails the structure, integrity or safety check, `metadata` is `null` | `404 lesson_not_found`, `404 lesson_not_available` |
| `GET /api/lessons/{id}/recordings/{name}` | After full validation passes, returns `{lesson_id, name, metadata, events}`. If validation fails, no events are returned | `404 recording_not_found` (including an invalid name), `409 recording_stale`, `422 recording_invalid` |

Every request validates again, using the keys currently configured in the backend. An error response contains neither the recording name, nor a location, nor anything that was detected.

Automated tests (`tests/test_recordings.py`) build lessons, run storage and recordings only in temporary directories and never write recording files into the repository. A real recording requires the user to run with a real model first and then export with the export script.
