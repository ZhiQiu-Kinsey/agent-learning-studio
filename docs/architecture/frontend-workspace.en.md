# Frontend structure

**English** · [简体中文](frontend-workspace.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

The frontend uses React, TypeScript, Vite and Tailwind CSS. The whole site has one visual motif, the **agent stage**: the stage, the context film strip, the timeline and the tool cards are all derived from real run events. An illustration uses the same stage renderer, but draws it with dashed lines and adds an "Illustration · not a run record" watermark.

## Pages

| Page | Entry | Content |
| --- | --- | --- |
| Home | `components/home/Home.tsx` | An agent-loop illustration (step through it or click to play; it doesn't start by itself after loading), the learning journey (real progress on this device), and continue where you left off |
| Onboarding (chapter 0) | `components/Onboarding.tsx` (subcomponents in `components/onboarding/`) | Seven preparatory chapters. Illustrations, quick checks, misconceptions and deep-dive blocks render in place. Checkpoints are self-reported and stored on this device |
| Curriculum map | `components/Curriculum.tsx` (subcomponents and data hooks in `components/curriculum/`) | Domain cards (MagicBento), a prerequisite roadmap (@xyflow/react + elkjs, lazy-loaded), and a list with search |
| Lesson page | `scenes/LessonScenes.tsx` | The lesson bar and five scenes: Understand / Code / Lab / Check / Review |

All five scenes implement `SceneProps` from `scenes/types.ts`. A scene mounts on first visit and keeps its state afterward. When a run is started from another scene, the page switches to the Lab scene automatically (if you are already in the Lab scene, it neither switches nor scrolls). Other components, such as the command palette, can call `requestScene()` to switch scenes.

- **Understand** (`UnderstandScene`): `content/blocks/UnderstandBlocks.tsx` renders the v2 blocks in the order the author arranged them, including concept cards, body text, step-by-step explanations, illustration stages, quick checks and predict-first prompts.
- **Code** (`CodeScene`): reads from `/api/lessons/{id}/code` the "New in this lesson" markers computed from the real source (it compares lesson code with the runtime text through the field `t.<field>`, and excludes platform code and test fixtures), line-numbered notes, and design decisions. A tool function can jump to the matching real `tool_result` in the Lab. By default it opens a file that has notes and shows only the annotated ranges: lines outside the ranges and platform code collapsed by `folds` shrink to one line, click to expand in place, and "Show the whole file" toggles the full view (`codeSegments` in `scenes/code/model.ts`). When a jump targets a collapsed line, it expands automatically. The file list marks files as "Platform", "Test fixture" and "Runtime text". For runtime text (`locales/`), only the file for the run language is listed, and it is fetched again together with the details when the UI language changes.
- **Lab** (`LabScene`): on a wide screen (≥1180px) it has two columns. The left column `.lab-rail` is fixed below the toolbar and scrolls inside the column when its content is too tall; the right column is the lab bench. On a narrow screen, the two cards of the left column sit above the lab bench.
  - Left column: the experiment card (hypothesis, arms, observation points) and the evidence check card (check progress, the guided tour, and a collapsible "What this experiment can tell you", collapsed by default).
    - Arms are the entry point for choosing an exercise (the `/` menu in the question bar is a shortcut). When you switch experiments, the first arm that can really run is selected. Arms that inject offline faults can't be selected.
    - Observation points are checked only against runs of this experiment's arms (`scenes/lab/experimentRun.ts`, decided by `runExerciseId`). Runs of other experiments stay on the stage, but here the label reads "Check after a run".
    - The observation point whose evidence is currently framed is highlighted (`data-current`). When a run ends, the first observation point that was found is selected by default, and the view doesn't fall back to replay.
  - Lab bench (`components/workspace/Laboratory.tsx` only assembles it; the parts live in `components/workspace/lab/`): one question bar at the top (the question on the left, the final answer and the connection on the right), and the run console below it. The run console contains: the stage (slightly shorter in the lab bench than elsewhere, about 18rem, with two lines per node: name, then type and status; the canvas grows taller when there are many tools. Events that arrive in batches during a run are advanced one by one by `stage/usePacedCursor.ts`, which replays at most the last 5 steps at about 0.45 seconds per step, and only on the stage; replay, dragging and reduced motion are not affected); the waiting-for-model state; the tool-call bar; replay and timeline; the event list and JSON inspector; the context film strip; tool cards; and the generic views.
  - The view follows the run (`scenes/lab/useRunFollow.ts`): when a run starts, the run console (`data-run-focus`) scrolls below the toolbar, and once the stage has played out the last few steps, the page returns to where it was when the run started (even a fast run stays for at least about 1.2 seconds). If the learner scrolls the page during the run, it no longer goes back by itself. With reduced motion, it jumps directly.
  - The lesson header image in the Lab scene keeps only the title and the scene label; the intro and the lesson goals appear in the other scenes.
  - Run language: when a run is created, it carries the UI language (`RunRequest.locale`). The backend resolves it against the run languages the lesson supports and writes it into `run_start.data.locale`. If the lesson doesn't yet have a runner for the UI language, a note appears under the question bar (`lab-runtime-locale`). If the run on screen differs from the UI language (for example, you switched to English but are still looking at a Chinese run), the answer area states the language of that run (`lab-run-locale`), the answer is marked with `lang`, and the content isn't translated. When the UI language changes, a question and preset parameters that weren't edited switch to the presets of the new run language, and edited ones are kept. Lesson recordings are labeled the same way, by the `locale` in their metadata.
  - Reusing the previous run (`hooks/runCache.ts`): after a run completes, the browser remembers which `run_id` goes with the hash of "this lesson, this exercise, the question, the parameters, the system prompt, the tool definitions, the run language, and the lesson and platform code" (it stores only the ID and the hash, not the question text). When you enter the lesson again or switch back to the exercise and none of these has changed, the events of that run are read back from run storage (`GET /api/runs/{id}/events`; replay is read-only), the model isn't called again, and a note under the question bar says "This is your previous run". The note disappears as soon as you change the question or a parameter. When the run records are cleared (404), the ID is forgotten.
  - Guided tour: after you click "Start the tour", the whole page dims and each step frames a single piece of evidence, with the explanation card next to it (`scenes/lab/GuideTour.tsx`, lazy-loaded). Each step has a short explanation. If it has an observation point, it jumps to the matching event and frames those lines in the JSON inspector (`components/workspace/lab/jsonLines.ts` lays the text out exactly as `JSON.stringify` does and records the field line numbers). The lab report frames the evidence board. When a step names only a stage role, it frames the stage node (if this run has no such node, it frames the whole stage; if the target still can't be found, the step is skipped in the direction of paging). The opening line and evidence that didn't appear in this run are shown centered, and the latter says plainly that it wasn't found. Clicking the dimmed area does nothing, and the framed area still scrolls and can be selected as usual. ← / → change steps and Esc exits. After exit, the page stays on the last piece of evidence and focus returns to "Start the tour". Lab keyboard shortcuts are disabled during the tour.
  - The "locate" action of an observation point shares its "evidence focus" with the tour (`components/workspace/lab/evidenceFocus.ts`): it switches to the execution record, selects the event, frames the field, and scrolls it into view.
  - The conclusion card; when recordings exist, a source switch appears.
- **Check** (`CheckScene`): the learner rates confidence before answering, and gets option-level feedback. The trace error hunt uses only the learner's own runs. Checkpoints are self-reported.
- **Review** (`ReviewScene`): shows only real records on this device and doesn't decide "mastered". The local learning badge (a 3D tag, lazy-loaded) prints only real numbers on its face.

## Modules

| Directory | Responsibility |
| --- | --- |
| `src/stage/` | `deriveStage` (a pure function: topology, spans, signals, film strip), `replay.ts` (the replay clock, with a version token), `AgentStage`, `ContextFilm`, `Timeline`, `ToolCards`, `Lenses` (generic views for the standard teaching event families) |
| `src/content/` | Generated v2 types `types.gen.ts`, `view.ts`, the selector engine `selector.ts`, tour `guide.ts`, prediction `predict.ts`, block rendering `blocks/`, and term and code-name annotation `glossary/` (terms come from `/api/glossary`; code names come from `code_names` in the lesson details, and their notes from `code_notes` in the content; for the rules see [Terminology and code names](terminology.en.md)) |
| `src/motion/` | `MotionProvider` (merges the system reduced-motion setting, WebGL and page visibility), `useMotionBudget` (pause when off-screen; there is no limit on simultaneous WebGL contexts on screen, decided by the maintainer on 2026-10-06), `revealProps` (scroll reveal), `EffectBoundary` (falls back to static when a decorative effect fails), the `MotionIntent` intent registry, and motion tokens |
| `src/i18n/` | i18next, the language registry, `locales/zh-CN/*.json` organized by namespace, and error-code translation |
| `src/progress/` | Learning progress on this device (localStorage, with its own version line and migration ladder). It records only real actions |
| `src/components/react-bits/` | Components adapted from React Bits (the first line of each file states the source and license). In longer components, shaders, constants and pure logic live in a directory with the same name (for example `ElectricLogo/shaders.ts`), while the component's file path and exports stay unchanged, which makes it easier to compare with upstream updates |
| `src/components/backdrops/` | Animated backgrounds for the hero band: `Backdrop` lazy-loads React Bits WebGL shaders by preset, unmounts when off-screen, and degrades to a same-color gradient when static. `backdropFor(category)` assigns each curriculum domain a mood. Dev preview: `/dev/backdrops.html` |
| `src/hooks/useStudio.ts` | Lessons, parameters, runs (`POST /api/runs`, resuming by seq after a disconnect) and replay state |
| `src/components/command/` | The ⌘K command palette (cmdk, lazy-loaded) |
| `src/components/shell/` | The sidebar (brand mark, "Before you start", the branching course tree) and shell effects |
| `src/components/toast/` | Global notifications: `notify()` reports only real results, and `ToastHost` displays them |
| `src/lib/` | Small utilities: lesson IDs, the color conversion `color.ts`, the link check `url.ts`, and so on |
| `src/scenes/lab/` | The lab panel, the tour (`guidePlan.ts` decides what each step frames, and `GuideTour.tsx` connects to the masked tour), the recording view, and lab keyboard shortcuts |
| `src/tour/` | The generic masked tour (React Joyride in controlled mode): mask and highlight frame, explanation card (React Bits `SpotlightCard`), progress bar, keyboard. `reveal.ts` scrolls first and then draws the highlight frame. It is independent of any lesson and reusable for other guides |
| `src/lesson-extensions/` | Lesson slots registered at build time. If an extension fails to load, the page falls back to the generic UI |
| `src/styles/` | Styles organized by module. `tokens.css` holds the design tokens and the motion-level switch |

## Honesty rules (UI layer)

- Run data comes only from real events. Illustration events carry `provenance=illustration`. A recording is labeled with its model and date and is not mixed into "my runs".
- While waiting for the model, the UI shows only "Waiting for the model response" and a real timer counted from the timestamp of the request event. It never says "thinking", and a non-streamed answer arrives all at once, with no typewriter effect.
- When a run is stopped, only tool calls that were still executing are marked "Stopped, no result". Results that had already completed are not overwritten.
- Streamed responses (`components/workspace/lab/streaming.ts`): the answer pane shows only the text assembled from the chunks that have arrived, appearing event by event with no typewriter effect. The timeline draws the chunks at the real `received_ms` of each `response_delta`, and at the end it says how the stream ended (completed / stopped / cancelled / error); a cancelled stream keeps only what arrived before the stop. The final `response` is labeled as assembled from chunks.
- Approvals (`components/workspace/lab/ApprovalPanel.tsx`, `approvals.ts`): when a run stops at `approval_requested` the UI shows an approval card (summary, arguments, risk, time left, an optional reason, and editable arguments when `editable`). Approve / reject is submitted through `POST /api/runs/{id}/approvals` with the argument digest in the body. A card is interactive only in the current run; in replay, recordings and the last run the same card is read-only and shows the record. While waiting, the run status reads "awaiting approval".
- Stop and disconnect: the Stop button sends `user_stop` and shows the end state only after the server's `done` arrives; "Disconnect events (run continues)" only closes the event stream and does not stop the run, and "Reconnect" continues from the last event.
- Checkpoints (the "Resume from “checkpoint name”" button in the `checkpoint` event detail) call `POST /api/runs/{id}/resume` to start a new run; the new run's answer pane names the source run and checkpoint and says that no old request was replayed.
- Elapsed time comes only from server timestamps. When replay compresses a very long real wait, it says so. When a response doesn't report usage, the UI shows only the character count and states why.
- SDK-standardized data is never labeled as a raw HTTP message.
- Progress records only actions that really happened. Preloading a lesson in the background doesn't count as "opening" it, and the same run_id is counted only once.

## Motion

- **Motion level**: `<html data-motion="full|static">` is written by the first-paint script and `MotionProvider`. It follows only the system's "reduce motion" setting, and there is no in-page switch.
- **CSS style**: always use `:root:not([data-motion="full"])`. Tailwind's `motion-reduce:` and `motion-safe:` already follow this attribute.
- **Heavy effects**: they connect through `MotionIntent` or `useMotionBudget`, load on demand, pause when off-screen, and all have a static fallback. There is no limit on simultaneous WebGL contexts on screen (decided by the maintainer on 2026-10-06: on the curriculum map, each domain card always shows its own animated background). An off-screen shader unmounts and calls `loseContext()` to release its context, so contexts don't pile up toward the browser's hard limit while scrolling (about 16 in Chrome, where old contexts are forcibly reclaimed). On the curriculum map, at most 12 were measured alive at the same time.
- **Decoration and data stay apart**: the animated hero backgrounds, entrance and scroll reveals, hover feedback and click sparks decorate only the static UI. Run data gets no decorative effects. Each real event emits one signal only, and the flowing border during a run appears only in a real run. Scroll reveal always uses `revealProps`. If the system turns on reduced motion midway, content that hasn't been scrolled to yet is shown in full immediately.

## Terms and code names

The lesson page wraps all scenes in `LessonVocabulary`, which provides the current lesson, the lesson's code names and the code notes.

- A term is underlined only at its first occurrence on each page (`GlossaryScope` decides ownership). `data-tier` distinguishes three tiers:
  - `new`: introduced in this lesson, solid gradient line;
  - `review`: introduced in an earlier lesson, dotted line;
  - `background`: background knowledge, dashed line.
- Names in this lesson's source (including message roles, event names and terminal run states) are shown in code style. Those with `code_notes` get a dotted line and show a note card on hover or focus.
- Matching order: code-styled fragments → terms → code names. A phrase in the glossary's `not_in` is skipped as a whole, so that Chinese substrings don't match by mistake.

## Text and multiple languages

- `zh-CN` (the source language) and `en` are registered (`src/i18n/locales.ts`). To add a language, add one entry to the registry and create `locales/<language>/*.json` with the same keys as zh-CN.
- All UI text lives in `locales/<language>/<namespace>.json`. `npm run i18n:check` checks the keys, placeholders and plural forms of every language. zh-CN uses plain keys only. A language that needs singular and plural forms can write the same key as `<key>_one` / `<key>_other`; in that case the source text must use `{{count}}`.
- `src/i18n/__tests__/hardcoded-cjk.test.ts` counts hard-coded Chinese text in components with an AST. The count may only go down, and it is currently 0.
- Backend errors carry a `code`, which the frontend translates. A provider name is looked up by `provider_id` in `settings:providerNames`. If there is no matching key, the server's name (the brand name) is used.
- Language switching: the `LocaleSwitch` in the top bar (the same GlideSelect as the theme) and the "Language" entry of the command palette both call `changeLocale`. The choice is stored in localStorage (`agent-lab-locale`), and `<html lang dir>` and the page title follow it. On a phone-width screen, the language and theme controls collapse into an icon with an arrow.
- Lesson content (the course catalog, lesson details, code, onboarding, the glossary) is requested with `?lang=` for the UI language (`withLocale` in `api.ts`). Every effect that fetches these endpoints lists `useContentLanguage()` as a dependency, and the shared caches are split by language (`lib/languageCache.ts`, `hooks/useCurriculum`, `useGlossary`, `useOnboarding`). Switching language refetches in place without reloading the page, and the current lesson, scene, exercise, inputs and the run on screen are all kept.
- Fallback and labeling: when a translation is missing, that piece of text shows the Chinese original. When the UI isn't Chinese, lesson text that is mainly Chinese gets `lang="zh-CN"` (`i18n/textLanguage.ts`; body text, titles, lesson names in navigation, the syllabus). When a whole lesson or onboarding has no translation, or only part of it, a note appears under the title (`TranslationNotice`).
- Terms and code names: English body text matches terms by their English names and aliases (see `content/glossary/match.ts`). In Chinese body text, every name from the source is shown as code. In English body text, only names that "look like code" (containing `_ . - ( ) :`, digits or an inner capital letter) are marked; ordinary words such as `messages` and `is` stay as plain text.
- Dates and numbers are always formatted with `Intl` and the current UI language. Components don't hard-code language codes.

## Validation

Unit tests use vitest (`npx vitest run`), and browser tests use Playwright. How browser tests locate elements:

- by role, `data-testid`, and the text keys read through `e2e/i18n.ts`;
- the selector baseline may only go down;
- `e2e/a11y.spec.ts` scans the main pages with axe-core against WCAG 2.1 A/AA.

For screenshot checks, use `scripts/capture-lab.mjs` and `scripts/capture-scenes.mjs`. For the commands, see [Development validation](validation.en.md).
