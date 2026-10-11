# Adding a lesson and customizing it

**English** · [简体中文](adding-lessons.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

An ordinary lesson only needs its own directory: implementation, experiments, teaching content and tests. Navigation, source viewing, model connection, stop, the event stream and replay are shared by the platform. A lesson with different teaching needs can write its own runner or its own frontend component.

## Shortest path to a new lesson

`curriculum/catalog.json` is the single source for lesson IDs, aliases, titles, summaries, learning objectives, levels, prerequisites and status. The displayed lesson number is computed from its directory order (see the next section). `lessons/lesson_*/lesson.json` describes where the implementation lives. The backend discovers these manifests automatically; you no longer edit `server/catalog.py` to add a branch.

The commands below use `document-loading`, a lesson that is still planned, as a demo; substitute your real lesson. `--id` accepts a lesson slug (or an old slug alias from before a rename). `--slug` may be omitted; if given, it must match the slug in the catalog (`document_loading` is also accepted). It is kept only for compatibility with old commands. The generator accepts only lessons that are already in the catalog with status `planned`. It validates the arguments, paths and duplicate manifests first, then creates files. It never overwrites an existing directory and never opens a lesson to learners by itself.

```powershell
# Preview the file list first; nothing is written
.\.venv\Scripts\python.exe scripts/new_lesson.py --id document-loading --dry-run
# Create a lesson that uses the generic agent loop
.\.venv\Scripts\python.exe scripts/new_lesson.py --id document-loading
# For a complex flow, use --kind custom instead (a directory can be created only once)
```

The generated directory is `lessons/lesson_document_loading/`. It contains `lesson.json`, `content.json`, `README.md`, `__init__.py` and a smoke test `test_lesson.py`. A native lesson also gets `main.py`, `tools.py` and `fixtures.py`; a custom lesson also gets `runtime.py`. Both kinds come with a `locales/` message catalog (`__init__.py`, `zh_CN.py`, `en.py`); the manifest's `runtime.locales` already lists both run languages, and the exercise questions are filled in per language (see "Multilingual runtime"). The sample only verifies that the wiring works; the prose and exercises are explicitly marked as still to be written.

1. Implement the lesson against the learning objectives and acceptance requirements in the catalog. Fill in the introduction, mechanism, examples, experiments, observation points and self-check, keeping the order "concept → minimal implementation → run evidence → experiment → self-check".
2. Run the lesson's own tests, for example `python -m unittest lessons.lesson_document_loading.test_lesson -v`. Add tests for real Python behavior, error handling, input and stop. A passing smoke example does not mean the lesson is done. `tests/test_lesson_local_suites.py` pulls each lesson's `test_lesson.py` into the full test run, so you don't register it anywhere.
3. Run `python scripts/validate_lessons.py`. It checks every implementation manifest, including author drafts that are still `planned`. Validation does not call a model, and passing structural validation does not mean the teaching acceptance check is done.
4. Only after the lesson passes acceptance, change its status in `curriculum/catalog.json` to `available`. Then run `python scripts/export_curriculum.py` and the full backend tests, and restart the server.
5. In the web UI, check navigation, the guide, source viewing, a real run, stop and replay. If you added frontend components, also build the frontend and run the relevant browser tests.

A `planned` lesson does not appear in the runnable API, even if its implementation directory is complete. An `available` lesson must have a valid manifest. Validation errors are shown in the developer terminal with the lesson and a local path; never show a raw exception stack to learners.

## Lesson IDs, aliases and displayed numbers

| Concept | Rule |
| --- | --- |
| Lesson ID (primary ID) | The `id` of each lesson in `catalog.json`: a stable kebab-case slug such as `tool-selection`. Regex `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`, at most 48 characters. APIs, events, links and frontend state use only this |
| Alias | Each lesson's `aliases`: old slugs from before a rename, used only to resolve old requests. APIs never return an alias as `id`. Numeric aliases are not accepted: the displayed number changes with directory order, so a numeric alias would be confused with it (all old numeric aliases were removed on 2026-10-03) |
| Displayed number | `number`, computed from 1 in `lessons` array order and never written in JSON. Inserting a new lesson changes only the numbers of the lessons after it, never any ID |
| References inside the catalog | Module `lesson_ids`, `prerequisites` and elective `prerequisites` are always slugs. If you write an alias by mistake, validation tells you which slug to use |

Validation (`index_catalog` in `server/curriculum.py`, shared by lesson loading, `validate_lessons.py`, `export_curriculum.py` and `new_lesson.py`):

- A slug must be well-formed and unique. An alias must be a kebab-case slug (not a number), must not collide with any slug or other alias, and must not equal its own lesson's slug.
- A lesson referenced as a prerequisite must exist and come before this lesson (which also rules out cycles). Prerequisites of electives must exist too.
- The traversal order category → module → lesson must match the `lessons` order, and each lesson is registered in exactly one module, so navigation and displayed numbers cannot drift apart.

**Implementation directory mapping:** the `id` in `lessons/*/lesson.json` must equal the lesson slug in the catalog (not an alias). This is the only mapping between a lesson and its implementation. The directory name only determines the Python package name and plays no part in identity. The first ten lessons keep the form `lesson_NN_<slug with underscores>` (for example `lesson_01_tool_selection` ↔ `tool-selection`); the number in these directory names is historical, not the lesson number, and they are not renamed for now. A new lesson is created by the generator as `lesson_<slug with underscores>` (for example `lesson_document_loading`), with no number prefix.

**API behavior:**

- `GET /api/lessons`, `GET /api/lessons/{id}` and `GET /api/curriculum` return the slug `id`, `number` and `aliases` for every lesson.
- The `lesson_id` of `GET /api/lessons/{id}` and `POST /api/runs` accepts a slug or an alias and is resolved to the slug internally. The `run_start` event and `RunContext.lesson_id` always record the slug.
- An ID that cannot be resolved returns 404 with the body `{"detail": "...", "code": "lesson_not_found"}`. A lesson that is registered in the catalog but still `planned` returns 404 with `lesson_not_available`. The error message does not echo the raw ID from the request.
- The frontend uses the slug as `lessonId` and shows the `number` returned by the API. A lesson ID that comes from an old link, an old export or local storage first goes through `resolveLessonId` in `frontend/src/lib/lessonIds.ts` to be migrated to a slug. (Currently no localStorage key stores a lesson ID; any new key added later, such as learning progress, must go through this step.)

## Glossary

`curriculum/glossary.json` is the single source for terms. `GET /api/glossary` returns it read-only, and `scripts/validate_lessons.py` validates it. Each term has these fields:

| Field | Required | Description |
| --- | --- | --- |
| `id` | Yes | kebab-case, unique in the whole table; content blocks will refer to it later with `term_id` |
| `zh` | Yes | The Chinese form. A word that is already used in English (Agent, Token, JSON Schema) is the same as `en`. The name must be specific; don't use common one-character words or verbs |
| `en` | Yes | The English name |
| `kind` | No | `concept` (course concept, the default) or `background` (background word, such as tokenizer or ablation; has no `first_lesson`) |
| `definition` | Yes | A short Chinese definition, at most 160 characters |
| `aliases` | No | Other ways the term is written in the text, such as `RAG` or `验收器`. Chinese names and aliases are unique across the whole table |
| `not_in` | No | Longer phrases that contain the term name but mean something different, such as `评估者` for the term `评估`. These phrases are not annotated as a whole in the text |
| `first_lesson` | No | Slug of the earliest runnable lesson that uses the concept. Not an alias. Omit it when the lesson is not yet registered (such as prompt caching or sandbox) |

The hover card title is shown as "中文（English）", or only once when `zh` and `en` are identical. Each term the API returns carries a computed `display` and `first_lesson_number`. A test checks that the term really appears in the catalog entry or teaching content of the lesson named by `first_lesson`, so a term cannot be registered for a lesson that doesn't teach it. For the admission criteria, how to write the four kinds of words (course concepts, background words, code names, ordinary words) and the unified wording table, see [Terminology and code names](terminology.en.md).

**Multiple languages:** the term mapping fields `id`, `zh`, `en`, `first_lesson` and `kind` are maintained only in the source file; the translation layer must not change them. `curriculum/glossary.<language>.json` is keyed by term `id` and provides three items: the display name `<id>.term`, the definition `<id>.definition`, and the aliases in that language `<id>.aliases` (an array of strings; write `[]` if there is no other name). The source text is `en`: if the English name changes, the display name and the aliases go stale together. `GET /api/glossary?lang=en` returns `term`, `local_aliases` and `definition_locale`. An entry without a translation uses `en` as the display name and falls back to the Chinese definition. In the English UI the hover card shows only the English name, and a fallback Chinese definition is marked `lang="zh-CN"`. English text matches terms by English name and aliases (case-insensitive, whole word, longest match first, plural endings allowed, hyphen treated as a space). Chinese aliases are kept for passages that fall back to Chinese.

## Pacing and code-reading rules (since 2026-10-03)

Basis: the pacing and code-reading audit of the 16 lessons (see [section 8 of the curriculum implementation plan](curriculum-plan-2026-10.md#8-第二轮节奏读码与课程表细化2026-10-03)). New and revised lessons follow the rules below; whatever can be checked automatically is already wired into `validate_lessons` and the tests.

### Pacing

- **One lesson teaches one thing.** A lesson introduces at most 5 course concepts (concept entries in the glossary whose `first_lesson` is this lesson). If you need a sixth, first consider splitting the lesson or moving it to the lesson before or after.
- **A paragraph introduces at most two new concepts**, and each section comes with a concrete example (real field names, real numbers). A lesson has 3–4 concept cards, covering only the few most central points.
- **Run once first.** Put the `predict` block before the first quick check: after two or three sections the learner can go to the lab bench for a first run, instead of reading the whole Understand scene first.
- **At most 3 experiments**, and at most 5 arms per experiment. Every experiment states `proves` and `does_not_prove`.
- **A lesson that does not call a model** says "this lesson does not call a model" in its summary and in the first section of the text.
- **To mention another lesson, write `{{lesson:<slug>}}`**, which the backend replaces with "Lesson N". Displayed numbers change when a lesson is inserted into the syllabus, so the text, the README and runtime strings never hard-code a lesson number (a test checks the lesson text).

### Code reading

| Rule | How | Check |
| --- | --- | --- |
| Read lesson code first | In `lesson.json`, list this lesson's files first in `sources`. List platform files (`course/`) only if the lesson really teaches them | The frontend labels "Platform" and "Test fixture" |
| At most about 40 lines per code block, at most 3 blocks per lesson | One block covers one responsibility. Split an overlong function into blocks, or put the lines unrelated to the lesson into `folds`. Code that isn't in a block can still be expanded in the file view | The block count is checked by `tests/test_code_reading.py`; line counts are a judgment call |
| Notes carry anchors | `notes[].anchor` is a piece of the original text that the line must contain. After source moves, run `scripts/realign_notes.py` | `validate_lessons` |
| Note density | In the displayed range, at least 1 note per 8 non-empty, unfolded lines, and no more than 12 consecutive lines without a note. Prefer function signatures, loop starts and stop conditions | `validate_lessons`, `tests/test_code_note_density.py` (old blocks sit in a baseline that can only shrink) |
| Fold platform code | Lines unrelated to the teaching point (event publishing, timing, report assembly) are collapsed with `folds: [{id, start, end, label}]`; the label says what was folded (for example "Platform: publish the report event") | A fold cannot contain notes |
| Inline comments | Comments and docstrings in `lessons/` and `course/` are written in English (the Chinese explanation lives in the code-reading notes, which exist in both Chinese and English). Write "why", not a restatement of the code. Number the steps of the main loop (`# 1.`, `# 2.`) | By hand; docstrings count toward the hard-coded Chinese baseline |
| New in this lesson | Computed by the backend from the lesson files under `lessons/`, excluding platform code and test fixtures | Automatic |

How to write a runner: put "record the evidence" at the boundaries. Model requests all go through `context.complete`, calls proposed by the model go through `context.execute_proposal`, and calls the runner initiates itself go through `context.call_tool`. Keep only the steps the lesson teaches in the lesson loop. Assemble the report event (`lesson.report`) in a `_report(...)` function, and either don't show it in a code block or collapse it with `folds`.

### Verification

- Offline: the lesson's tests, all backend tests, `validate_lessons`, `migrate_content.py --check`. If you changed the frontend, also run the build, vitest, i18n and the relevant Playwright tests.
- Real model: run every exercise for real at least once (`POST /api/runs`, `mode: live`) and check that the events, the report and what the text says agree. Write the result in the execution log. The text does not presuppose the result of a real run; it only describes how to judge from the events.

## An implementation manifest

```json
{
  "schema_version": 1,
  "id": "document-loading",
  "content": "content.json",
  "sources": [
    { "path": "lessons/lesson_document_loading/main.py", "language": "python" },
    { "path": "lessons/lesson_document_loading/tools.py", "language": "python" },
    { "path": "lessons/lesson_document_loading/locales/zh_CN.py", "language": "python", "locale": "zh-CN" },
    { "path": "lessons/lesson_document_loading/locales/en.py", "language": "python", "locale": "en" },
    { "path": "course/runner.py", "language": "python" }
  ],
  "exercises": [
    { "id": "small-context", "title": "短上下文实验",
      "question": { "zh-CN": "本课实际问题", "en": "The real question of this lesson" } }
  ],
  "runtime": {
    "kind": "native",
    "entrypoint": "main",
    "max_rounds": 3,
    "requires_model": true,
    "locales": ["zh-CN", "en"]
  },
  "testing": { "completion_factory": "fixtures:create_completion" }
}
```

`content` is relative to the lesson directory. `sources.path` is relative to the project root and must fall within the course and platform source that may be made public. Do not add local keys or configuration. The execution entry point and the test factory point only to trusted Python modules inside the same lesson; paths or import addresses are never passed in from the browser. Different lessons may use the same exercise ID, and test fixtures are isolated per lesson.

`main.py` exports `setup(locale)`, which returns `course.runner.AgentSetup(system_prompt, tools, available_tools)`; that is enough to reuse the native tool loop. It supplies the system prompt and tool definitions in the run language (see "Multilingual runtime" below). Each lesson may reference existing tools that have no side effects, and the source manifest should show the implementation that is really referenced. The generic loop handles model requests, tool calls and results, errors and the round limit.

The deterministic fixture is a `create_completion(exercise_id, inputs=None, locale="zh-CN")` factory inside the lesson. It returns `completion(body, api_key)`. A lesson that supports several run languages gives the deterministic answer in the language given by `locale`. A test response may simulate the model's decisions, but the Python tools must actually execute. A fixture is not a stand-in for the model in the learner web UI and does not interpret free-form input. A test exercise that needs injected input can set `offline_only: true` (it cannot be run for real in the web UI). If you want learners to examine a failure path hands-on in the web UI, prefer turning it into a local exercise: in a custom runner, have the runner construct the faulty call (`context.submit_call`) and declare `requires_model: false` on that exercise. The two fault-injection groups in `fail-safely` are an example.

## Teaching content (content v2)

`content.json` declares "how to teach". Its structure is defined solely by the Pydantic models in `server/content_schema.py`. The `$schema` at the top of the file points to `curriculum/schema/content.v2.schema.json`, which editors can use for completion. The basic skeleton:

```text
{ "$schema": "...", "schema_version": 2, "lesson": "<slug>", "source_language": "zh-CN",
  "capabilities": ["tools", ...],
  "scenes": {
    "understand": { "blocks": [hero, concepts, prose, micro-quiz, walkthrough, flow, predict, ...] },
    "code":       { "blocks": [whats-new, annotated-source, decision] },
    "lab":        { "experiments": [...], "inputs": [...] },
    "check":      { "blocks": [quiz, trace-hunt, checkpoint] } },
  "illustrations": { "<id>": { "events": [...] } } }
```

- **Blocks and ids**: every block and item has a stable id, and block ids are unique across the whole document. Block types are independent of scenes, and the scene order is fixed. Presentation is written only as semantic intent (such as `"reveal": "split"`), and the frontend motion layer maps it to concrete components.
- **Deep dive (`deep-dive`)**: holds background, mechanisms and worked examples that sit outside the main line. Its fields are `title`, an optional `summary` (the one-line sentence shown when collapsed) and `paragraphs` (Markdown).
  - It is collapsed by default in the web UI, and the main line must not depend on it: the lesson can be completed without reading it, and the lesson's core concepts must not live only here.
  - It is not a "section" and does not count toward the pacing rule "at least one quick check in every three consecutive explanatory passages". Terms, code names and wording inside `summary` and `paragraphs` are checked as usual.
  - The Understand page renders it at the position the author put it. In onboarding chapters, `deep-dive`, like `flow`, `micro-quiz` and `misconception`, follows the section before it.
- **Experiments**: each experiment in `experiments` consists of:
  - `hypothesis`: a testable hypothesis;
  - `arms`: the arms, which refer to exercises in lesson.json through `exercise`;
  - `observe`: observation points, with a selector (conditions `event`, `round`, `path`, `span_kind`, `name`, optionally `nth`);
  - `guide`: the guided tour. Each step is `{ "text", "observe"?, "stage"? }`: a short explanation (one or two sentences) plus the place to look while reading it. `observe` refers to an observation point; in the learner's own run the UI jumps to the evidence and frames it with a mask (for JSON fields, down to the line). `stage` names the stage role the step is about (`user`, `runtime`, `model`, `tool`, `memory`); without `observe` the step frames that node. A step with neither is shown centered and is used only as an opening. Every observation point must be covered, and no two steps repeat each other. An observation selector matches the first matching event, and a path counts as a hit as long as it exists (a null value counts too). When there are several events of the same kind, pin the target with `round` or with a field that only appears on the target event. Only when there really is no field to pin on (such as the second `tool_call` in the same round) write `nth`, which takes the n-th hit in run order (counting from 1); otherwise the tour frames a different event. `nth` depends on event order, and the order and count in a real run may differ from the deterministic run, so prefer a field whenever one can pin the target. To point at one metric or check inside a report, give that entry a stable `id` and write the path as `data.metrics[id=<id>]` (the first object in the array whose `id` equals it), not a positional path like `data.metrics[5]`: positions shift when the report gains or loses entries;
  - `conclusion`: `proves` states what it can prove, `does_not_prove` what it cannot.

  The selector semantics are implemented jointly by `server/selectors.py` and `frontend/src/content/selector.ts`, and both run the same shared test vectors. `tests/test_lesson_experiments.py` runs the deterministic run and checks that every observation point and every guide target can be hit. Evidence that cannot be found in that run is shown honestly in the UI as "This evidence did not appear in this run".
- **Prediction**: `predict` may use only rules that can be computed from real events (`count_events`), and compares only against the learner's own run; illustrations and recordings do not count. When an experiment has several arms, name the predicted arm with `arm`, and the arm that the question names in quotation marks (“…” in the Chinese source) must be the same one. The web UI judges only with runs of that arm's exercise; when the screen shows a run of a different exercise it displays "Run this exercise first".
- **Illustrations**: a `flow` block refers to a synthetic event sequence in `illustrations`. These events must pass the contract in `server/illustrations.py`:
  - calls and results come in pairs;
  - call ids use example ids (containing `example`);
  - no measured execution values such as duration, usage or cost appear.

  A `walkthrough` is an author-written step-by-step explanation, and the UI always labels it "Illustration · not a run record".
- **Parameter labels**: the `INPUT_MODEL` of a custom runner exports a JSON Schema, and the frontend generates parameter controls from it. The labels, help text and option text of the controls are written in `lab.inputs`, and a test guarantees they correspond one-to-one with the model fields. Use `Literal` for enums, not a regex `pattern`.
- **Code-reading blocks**: the path of an `annotated-source` must be in the lesson's sources, and the line numbers must really exist. "New in this lesson" is computed by the backend from the source AST; don't write it by hand.
- **Terms and code names**: a course concept is written as "中文（English）" only at its first occurrence in the introducing lesson (`first_lesson`); other lessons write the Chinese only. Background words are never written with an English pair. Source names mentioned in the text are automatically shown as code style, and any that need explanation get a note in the top-level `code_notes` of `content.json`. For the complete rules and the unified wording table, see [Terminology and code names](terminology.en.md). After writing, run `scripts/term_report.py --lesson <slug> --full`; `validate_lessons` rejects runnable lessons with wording problems. (These "中文（English）" rules apply to the Chinese source text. English text writes the glossary `en` name once; see "Translation layers" below.)

**Versions and migration**: old-version content goes through the migration ladder in `server/content_migrations.py` when it is loaded. To write it back to disk and normalize its format, use `scripts/migrate_content.py`; add `--check` to check only. After changing the schema, run `scripts/export_content_schema.py`, then run `npm run content:types` in the frontend directory. A test checks that the three stay in sync.

**Translation layers (multiple languages)**: the source language is zh-CN. Other languages are translation layers next to the source file, all in one format: `{"schema_version": 1, "locale": "en", "texts": {path: {"text": translation, "source": digest of source text}}}`. The web UI requests `?lang=<language>` according to the UI language and merges entry by entry. A missing or stale entry (the source text changed, so the digest no longer matches) falls back to the source text. A corrupt file, or one that writes a non-translatable path, falls back as a whole.

| Source file | Translation layer | Translatable paths (keyed by id) | Rules |
| --- | --- | --- | --- |
| `lessons/*/content.json` | `content.<language>.json` | `hero.headline`, `concepts.<item>.title`, `inputs.<field>.label`, etc. | `server/content_overlay.py` |
| `curriculum/onboarding.json` | `onboarding.<language>.json` | As above, prefixed with the chapter id | As above |
| `curriculum/catalog.json` | `catalog.<language>.json` | `category.<id>.title`, `module.<id>.description`, `lesson.<slug>.title/summary/objectives.<n>/topics.<n>/acceptance.<n>/experiments.<n>.steps.<m>`, `sections.<n>.gist` of planned lessons, `elective.<id>.*`, `source.<id>.role/adaptation`, `principles.<n>`, `title` | `server/data_overlay.py` |
| `curriculum/glossary.json` | `glossary.<language>.json` | `<term id>.term/definition/aliases` | As above |
| `lessons/*/lesson.json` | `lesson.<language>.json` | `subtitle`, `exercises.<exercise id>.title`, `ui.question_label`, `ui.question_help` | As above |

Fact fields cannot be overridden: ids, slugs, status, prerequisites, duration, difficulty, correct answers, code, selectors, URLs, and an exercise's `question` and preset inputs (they are sent to the model verbatim and are facts of the run). Source code, system prompts and run events likewise do not pass through the translation layer. Runtime text is written per run language in `lesson.json` and the `locales/` message catalogs; see "Multilingual runtime" below. Lesson level and difficulty are fixed values; the API adds `level_code` and `difficulty_code`, and the UI translates by code. In a translation, `{{lesson:<slug>}}` is written as "Lesson N" in the target language; text that has not been translated still reads "第 N 课".

Translate with `scripts/translation_kit.py`. The target is `lesson:<slug>`, `onboarding`, `catalog`, `glossary` or `manifest:<slug>`:

```powershell
.\.venv\Scripts\python.exe scripts/translation_kit.py status --locale en                       # coverage and stale count per target
.\.venv\Scripts\python.exe scripts/translation_kit.py export catalog --locale en -o todo.json  # export only missing or stale entries; --all exports everything
.\.venv\Scripts\python.exe scripts/translation_kit.py apply catalog --locale en -i done.json --check   # validate only
.\.venv\Scripts\python.exe scripts/translation_kit.py apply catalog --locale en -i done.json   # merge and write back, recording the source digest automatically
```

`apply` rejects non-translatable paths, and translations whose placeholders (`{{...}}`) or inline code (backticks) do not match the source text. In English translations, terms always use the glossary `en` name, titles are sentence case (only the first letter capitalized), and code names, event names and field names are kept as they are. `scripts/validate_lessons.py` reports the coverage of every translation layer, and structural errors fail it outright.

**Recording with the lesson**: after a real model run, export it unchanged to `lessons/<directory>/recordings/` with `scripts/export_recording.py --run <run_id> --name <name>`. A recording can come only from a live run. It carries a source hash and an integrity hash, and after the source changes you are prompted to record again.

## Multilingual runtime

The UI and lesson text are shown in the UI language (the translation layers in the previous section). The runtime is multilingual too: when an exercise is run from the English UI, all text the program sends to the model and writes into events is English. That covers the system prompt, tool descriptions, tool errors, the exercise question and preset inputs, the labels and values of `lesson.*` reports, answers written by the program, and `course/` platform messages. A run from the Chinese UI is exactly as it was before. The language is part of the run: it is fixed when the run is created, recorded in `run_start`, and replay shows it as recorded.

### How the run language is chosen

1. When the frontend creates a run it sends the UI language: the `locale` of `POST /api/runs`.
2. The backend resolves the run language from the lesson's `runtime.locales` in `lesson.json` (just `["zh-CN"]` if not written). The rule is `resolve_locale` in `course/i18n.py`: an exact match wins; next comes another regional form of the same language (`en-US` → `en`, `zh-TW` → `zh-CN`); if neither exists it uses the source language `zh-CN`. A malformed language code returns 422.
3. `RunContext.locale` is the resolved language. `run_start.data.locale` records it, and on a fallback `requested_locale` is recorded too. The run store's `runs.locale` and `GET /api/runs` carry it as well (runs from before this column was added count as `zh-CN`). Recording metadata (version 2) carries `locale`, which must match `run_start` and be in the lesson's `runtime.locales`.
4. `GET /api/lessons/{id}?lang=` and `/code?lang=` return `runtime_locale` by the same rule: the exercise questions, preset inputs, system prompt, tool definitions and runtime text files are all in that language. If the lesson doesn't yet support the UI language, the English UI shows the Chinese questions and Chinese source, and the lab bench says that the lesson's runner only has a Chinese version for now. When the run on screen differs from the UI language, the answer area says that this run was recorded in Chinese.

### Message catalog (`locales/`)

Runtime text lives in typed message catalogs, one Python file per language:

```text
lessons/<directory>/locales/__init__.py   Texts: a frozen dataclass, one field per message; texts_for = catalog(__name__, Texts)
lessons/<directory>/locales/zh_CN.py      TEXTS = Texts(...)   source language
lessons/<directory>/locales/en.py         TEXTS = Texts(...)
```

- In code, `t = texts_for(context.locale)`, then use `t.system_prompt`, `t.report_title`. A message with variables uses named placeholders, `t.unknown_tool.format(name=name)`; never concatenate strings (word order differs between languages).
- A field can be a string, a tuple of strings or a `{key: string}` dict. A `Texts` with a missing field fails at import. `tests/test_runtime_locales.py` then compares the two languages leaf by leaf for structure, type and placeholders, and checks that the English catalog contains no Chinese.
- A module shared by several lessons has its own catalog. For example, `lessons/lesson_01_tool_selection/locales/tools/` holds only the tool descriptions and errors of `tools.py`; each lesson's own system prompt lives in that lesson's `locales/`.
- Platform messages (unknown tool, arguments not an object, rounds used up, stop, model-call limit exceeded, Bailian connection errors, command-line hints) are in `course/locales/`. A programming error that only developers see is written directly in English and does not go into a catalog.
- For a language that the platform supports but this package has no file for, `texts_for` falls back to the source language, so a Chinese-only lesson runs as usual under an English request. A string that is not a run language (such as `fr`) is a programming error.

**Why not gettext, Babel or Fluent:** prompts are long and structured, and learners need to read word for word the exact text that is sent. A message catalog is plain Python data, so the file shown on the code-reading page is the text the runtime uses. gettext uses a piece of source-language text as the message id, so a Chinese reader of the code sees only English ids (or the reverse) and never sees the full prompt in the other language. We hardly need plurals or date formatting in runtime text, and a typed dataclass plus one generic test is enough to guarantee that every language has all fields and the placeholders match.

### Manifest and presets

- `runtime.locales`: the run languages of the lesson. It must include the source language `zh-CN`, and every entry must be in the platform's `RUNTIME_LOCALES`.
- An exercise's `question`, and the natural-language values in `inputs` and `input_defaults`, are written per language as `{"zh-CN": "…", "en": "…"}`. Numbers, booleans and code values (such as `Literal` options) are written as plain scalars. In a lesson that supports several run languages, a scalar that contains Chinese is rejected. An object means only "filled in per language", and its keys must be exactly the lesson's run languages.
- Natural-language fields of `INPUT_MODEL` get no Chinese default (no default at all; `input_defaults` supplies it per language). Otherwise the parameter form in the English UI would show Chinese, and an English run with an explicitly submitted `{}` would carry Chinese too.
- The labels, help text and option text of input controls are still written in `lab.inputs` in `content.json` and go through the translation layer.
- After loading, `spec["exercises"]` and `spec["input_defaults"]` are the source-language copy, and each language's presets are in `spec["presets"][locale]`. The backend reads them with `run_locale` and `lesson_presets` in `server/catalog.py`.

### Native lessons and custom runners

- A native lesson's `main.py` exports `setup(locale) -> AgentSetup`. The system prompt comes from the lesson directory, tool definitions are generated by `tool_definitions(locale)` (tool names and parameter names are code and the same in every language; only descriptions are translated), and the allowlist is generated by `available_tools(locale)`. When a tool function needs error text, put the message catalog first as a **positional-only parameter** (`def add_numbers(t, /, a, b)`) and bind it with `functools.partial`. The model's arguments are always passed by name, so it cannot replace this parameter, and an extra argument is still a `TypeError`.
- A custom runner takes `t = texts_for(context.locale)` at the start of `run(context)` and uses `t` for reports, task cards, reminders and answers written by the program.
- Functions in `course/` take a `locale` parameter: `execute_tool(call, tools, locale)`, `run_agent(..., locale=)`, `send_bailian(..., locale=)`, `SDKCompletion(profile, locale)`. `RunContext` passes it automatically.
- Command line: `main(locale=None)` reads `--locale en` with `course.i18n.cli_locale()`; `main.py --locale en` in the repository root works the same way.

### Code-reading page

- Language files in `sources` carry `locale` (the file names must be `zh_CN.py` and `en.py`), and one directory must register every run language of the lesson. Language-independent files such as `__init__.py` don't carry one. The API returns only the copy for the run language, with the role `texts` (labelled "Runtime text" in the UI).
- "New in this lesson" also compares runtime text: each `TEXTS` field is recorded as `t.<field>` and compared in the source-language copy, so a changed prompt shows up as a change, and the conclusion is the same in every language.
- Runtime text can also be a code-reading block (needed by lessons that explain a prompt sentence by sentence). The block is written on the source-language file with `start` and `end`; the start and end lines, notes and folds all land inside fields. The fields a block covers have the same number of lines in every language (English corresponds line by line to Chinese, and validation checks this). In the English UI the platform maps the block to `en.py` by "which line of which field", and the note text goes through the translation layer. Runtime text covered by a code-reading block also counts toward note density.

### Test fixtures and checks

- A fixture is written as `create_completion(exercise_id, inputs=None, locale="zh-CN")`, and the deterministic answer varies by `locale`. The leading marker uses `offline_marker(locale)` from `server/offline.py` (in English it is `[Offline script answer] `), and `result_answer(results, locale)` works the same way.
- `tests/test_runtime_locales.py`: every lesson × every exercise × every run language of the lesson runs through offline. All events of an English run (request bodies, tool results, reports, answers, `run_start`) contain no Chinese. A Chinese run is still Chinese. The message catalogs correspond field by field. The input schema of an English-capable lesson contains no Chinese. Language fallback and the `?lang=` endpoints are covered too.
- `tests/test_lesson_experiments.py` checks observation-point and guide hits under every run language: selectors may look only at event structure and must not depend on the text of any language.
- `scripts/cjk_baseline.py --check` (`tests/test_python_cjk_baseline.py`): string literals (docstrings included) containing Chinese in the Python files of `course/` and `lessons/` may only decrease. `locales/zh_CN.py` and test files are exempt.
- Lesson text and runtime text stay consistent: the Chinese text quotes the original from the Chinese catalog, and the English translation layer quotes the original from the English catalog (no more "Chinese original plus English gloss"). After source moves, re-align code-reading notes with `realign_notes.py` and review both the Chinese and the English notes.

The step-by-step checklist for converting a lesson (for people and agents doing the conversion) is in `.claude/briefs/i18n/convert-lesson.md`.

## Custom runners

With `--kind custom`, the manifest uses `runtime.kind: custom` and `entrypoint: runtime:run`. A custom lesson can implement branches, graph execution, several stages or local algorithms, and reuse the generic loop where needed.

```python
from pydantic import Field
from course.execution import LessonInputs, RunContext
from lessons.lesson_document_loading.locales import texts_for


class Inputs(LessonInputs):
    # No default: lesson.json supplies the preset in the run's language.
    label: str = Field(min_length=1, max_length=200)


INPUT_MODEL = Inputs


def run(context: RunContext):
    t = texts_for(context.locale)
    context.check_cancelled()
    context.emit("lesson.step", {"title": t.step_title, "label": context.inputs["label"]})
    return t.done.format(label=context.inputs["label"])
```

The frontend merges the lesson's `input_defaults` with the exercise's `inputs` and shows the result in an editable JSON box. When a request doesn't pass `inputs`, the backend uses this merged preset. `inputs` that are submitted explicitly (including `{}`) go straight to the lesson's `INPUT_MODEL` for validation, without quietly adding back parameters the learner deleted in the UI. The model must inherit from `LessonInputs`; unknown fields are rejected, and omitted fields can use Pydantic field defaults. `context.inputs` is the validated dict. A lesson that declares no input model rejects extra input by default. `question`, `exercise_id`, `lesson_id` and `mode` can be read from the context. A native lesson's question cannot be empty; a custom lesson may use structured input alone and validates the fields its task needs by itself.

The purely local lesson above should declare `requires_model: false`: it needs no key to be configured and fakes no model request. A single exercise in a custom lesson can also declare `requires_model: false` in `exercises`: that exercise does not connect to a model (`context.completion` is empty), and the UI shows it as a local run; the other exercises follow the lesson's declaration. A custom lesson that needs a model declares `requires_model: true` and uses these platform methods:

| Method | Purpose |
| --- | --- |
| `context.complete(body, round_number=1, branch=None)` | Uses the current model connection and records the request, the response and how they are represented. When sending several requests in parallel, give each branch a different `branch`; the timeline pairs requests and responses by it |
| `context.execute_proposal(tool_call, available_tools)` | Executes one call proposed by the model: records the proposed call and the tool result, paired by the same call id. When a provider omits the call id or sends an empty one, the platform fills in a `synthesized_call_<round>_<index>` that is deterministic within the run and writes it back onto the call itself (so the assistant message and tool message the lesson puts back into the history share one id, and the next round's request is well-formed), and the `tool_call` event is marked `id_synthesized: true`. The recorded `response` stays as the provider sent it. Such a call is not rejected, because the model really did propose it, and rejecting it would hide the real proposal. The events attach to the round of the most recent `complete`, with no per-branch distinction: no lesson currently executes proposals inside parallel branches, and to do so you would first add explicit round and branch parameters |
| `context.call_tool(name, arguments, available_tools, round_number=1)` | The runner (not the model) initiates one call to a registered tool, and the call and result are recorded |
| `context.submit_call(name, raw_arguments, available_tools, round_number=1)` | The runner submits a call as is (the name may be unregistered; the arguments are a raw JSON string and may be broken), going through the same checks as a call proposed by the model. It is used to demonstrate rejection paths. The events are marked as runner-initiated (`origin: course_program`; the UI shows "Runner calls a tool") |
| `context.run_native(module, max_rounds=3)` | Reuses a native sub-flow. Its answer is recorded as `lesson.stage_result`, and the returned string is for the outer runner to assemble the final answer |
| `context.emit("lesson.step", data)` | Records lesson-specific JSON evidence; custom events use the `lesson.` prefix |
| `context.check_cancelled()` | Responds to the platform's stop request before stages and side-effecting operations |
| `context.locale` | The language of this run (`zh-CN`, `en`). Lesson code gets runtime text with `texts_for(context.locale)` |

A runner can be a synchronous or asynchronous function. When it returns a string, the platform records the final answer automatically; it can also publish `answer` itself and return `None`. Start, end and the execution lock are managed by the platform, and a lesson cannot forge lifecycle events. The shared service keeps model connection, event snapshots, redaction and replay in one place. Do not build a separate SSE from a lesson, read keys directly around the connection management, or trigger execution from replay.

Stop is cooperative: a long loop needs checks inserted, and network requests already sent are still bound by the transport timeout. Trusted lesson code in a local process is not a sandbox. When you add a database, persistent memory, retrieval or a framework, you still have to implement a clear state lifecycle, an adapter and tests for that capability. `lessons/lesson_10_persistent_memory/store.py` provides a teaching SQLite persistent-memory implementation (`persistent-memory` teaches saving, reopening and recall; `memory-lifecycle` teaches version conflicts, expiry and scope), which you can use as a reference. The shared extension interface itself provides no general memory service.

## Custom pages and visualizations

When the interaction really is different, you can write a component for the lesson in `frontend/src/lesson-extensions/` and register it in `registry.ts` with a build-time trusted import:

```json
{
  "ui": {
    "lab": "structured-inputs",
    "inspector": "tool-outcomes"
  },
  "input_defaults": { "label": "样本" }
}
```

The three slots are `guide`, `lab` and `inspector`. `structured-inputs` is the shared structured-input panel, `tool-outcomes` shows tool results, and `evidence-board` shows the checks, metrics and comparison tables in the actual events. A lesson with no slot set keeps using the generic page. A fixed-task experiment can configure `ui.question_label` and `ui.question_help` to make clear that the question box is only the learner's note, so learners don't think they are changing the controlled experiment conditions.

`evidence-board` consumes the `lesson.report` event at the current replay position. `title` and `summary` are text. `checks` is an array of `{label, passed, detail}`. `metrics` is an array of `{label, value}` (both can carry a stable `id`, so observation points can select with `[id=…]`). The optional `table` is `{columns: string[], rows: (string|number|boolean)[][]}`. One run can publish several reports (draft, repair, final and so on), and the UI lets you select one and view the raw event. Only checks that were really executed can be marked as passed; items that were not executed should be omitted or given no `passed`.

Metric values and table cells are displayed by the shape of the value (`frontend/src/lesson-extensions/shared/reportValue.ts`): numbers use the large metric font; short text uses the body font; text longer than 32 characters (160 in a table cell) or containing line breaks takes a row of its own and is collapsed to four lines by default; objects and strings whose content is a JSON object (such as provider usage) are shown as a key-value list, with nested keys joined by dots. The value itself is not rewritten and stays as it was in the raw record.

A component uses shared state through `studio`, composes the default page through `children`, and respects `active` to pause off-screen motion. A dedicated observation chart should use the events at the current replay position, and must not always show the final state of the full history. Unknown keys and load or render failures fall back to the default view; JSON cannot dynamically load arbitrary URLs, scripts or HTML. After adding a component you still need to build the frontend; a content-only or Python-only lesson update usually needs only a backend restart.

## Tool limits

`--root` points to another project or test root, and the directory must contain `curriculum/catalog.json`. The generator rejects an invalid slug, a `--slug` that doesn't match the catalog, an unknown or already available lesson, a duplicate lesson manifest (whether the manifest uses the slug or an alias), and a target that already exists. A directory that escapes the project through a link is also rejected. If writing is interrupted, a partly created new directory may be left behind; the tool reports the error and keeps the files for inspection, and does not delete or overwrite existing work.
