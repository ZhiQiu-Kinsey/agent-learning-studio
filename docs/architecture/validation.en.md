# Development verification

**English** · [简体中文](validation.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

The backend tests check the following: the course catalog, manifests, the content v2 schema, migrations and the translation layer, the illustration contract, whether experiment selectors hit, lesson vocabulary (terms, bilingual pairing, bare English words, code notes), English text (no Chinese, "not reported", no Chinese-plus-gloss quotes), the pacing and code-reading rules (at most 5 new concepts per lesson, `predict` before the first quick check, annotation anchors and density, no hard-coded lesson numbers in lesson text or source), input validation, execution budgets, cancellation, model adapters, the event envelope, the run store, recordings and SQLite memory. The frontend unit tests (vitest) cover stage derivation, the replay clock, selectors, the guided tour, predictions, progress migration and keyboard shortcuts. The browser tests cover the home page, the onboarding, the curriculum map, the five scenes, running and replay, the command palette, themes, reduced motion, responsive layout, accessibility (axe-core) and the fallback of trusted extensions.

## Backend and lesson data

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/validate_lessons.py
.\.venv\Scripts\python.exe scripts/export_curriculum.py --check
.\.venv\Scripts\python.exe scripts/migrate_content.py --check
.\.venv\Scripts\python.exe scripts/term_report.py           # vocabulary problems per lesson; add --lesson <slug> --full for details
```

When a source change moves the annotation line numbers, first run `scripts/realign_notes.py` to realign them by anchor, then run `validate_lessons`.

Do not run `npm --prefix frontend exec vitest run` from the repository root: that does not read `frontend/vitest.config.ts` and would pick up the Playwright specs as unit tests. Use `npm --prefix frontend run test`.

Checks related to the run language (Chinese, English):

```powershell
.\.venv\Scripts\python.exe scripts/cjk_baseline.py --check       # hard-coded Chinese in course/ and lessons/ may only decrease (locales/zh_CN.py and test files are exempt)
.\.venv\Scripts\python.exe scripts/export_curriculum.py --check  # both the Chinese and the English course outlines must be in sync
```

`tests/test_runtime_locales.py` runs every exercise of every lesson offline in each run language the lesson supports. It checks that all events of an English run contain no Chinese, that a Chinese run stays Chinese, that the message catalogs correspond field by field (placeholders match), and that an English lesson's input schema has no Chinese default values. It also checks language fallback, the run store's `locale` column, and the lesson detail and code-reading endpoints under `?lang=`. `tests/test_lesson_experiments.py` checks that observation points and guided tours hit in every run language.

English text has three more checks (`validate_lessons.py` and `tests/test_english_text.py`): the English translation overlays, the English runtime text (`locales/**/en.py`, `en.md`) and the English UI strings must contain no Chinese (except the `ENGLISH_CJK_ALLOWED` allowlist, where every entry states a reason and unused entries must be removed); numbers the provider did not report are written "not reported", not "unknown"; and the old `"中文" ("gloss")` form, quoting the Chinese original with an English gloss, must not come back. The rules and the allowlist are in section 5 of [Terms and code names](terminology.en.md).

Manifest validation includes `planned` drafts but does not unlock a lesson. The vocabulary check applies only to runnable lessons; whether a Chinese term has been added to the glossary depends on the author reading the text through, see [Terms and code names](terminology.en.md). A new lesson needs both structural validation and real behavior and teaching acceptance.

## Frontend and browser

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test        # vitest pure-logic unit tests, including content types, i18n and the selector baseline
npm.cmd --prefix frontend run i18n:check  # translation keys, placeholders and plural forms are consistent across languages
.\.venv\Scripts\python.exe run_web.py
# keep the backend running; in another terminal:
Set-Location frontend
npx.cmd playwright test
```

Browser tests visit http://127.0.0.1:8765 by default and use the system Chrome. Set `AGENT_LAB_URL` to point them elsewhere. The existing specs run under zh-CN (`locale` in `playwright.config.ts`) and read the Chinese UI text through `t()` in `e2e/i18n.ts`. `e2e/locale.spec.ts` switches to English and uses `tIn("en", …)` to assert:

- the English UI, language persistence and `<html lang>`;
- lessons that have a translation show English, while lessons without one stay Chinese and carry `lang="zh-CN"`;
- the run part: creating a run sends the UI language, the answer of an English run is English, and after the language is switched the Chinese run on screen is labelled "这是一次中文运行" ("this is a Chinese run");
- for lessons whose runner is still Chinese-only, the English UI says so.

The whole browser suite needs no model key: the specs change the status to "configured" at the network boundary, and runs go through offline test mode.

## Translation layer

```powershell
.\.venv\Scripts\python.exe scripts/translation_kit.py status --locale en   # coverage and stale count per target
```

`validate_lessons.py` also lists the coverage of every translation layer (lesson content, onboarding, course catalog, glossary, manifest). Structural errors, non-translatable paths and wrong lesson references fail outright; missing and stale entries are only reported. `tests/test_content_overlay.py` and `tests/test_data_overlay.py` check paths, fact protection, stale fallback, the `?lang=` endpoints and each target of the translation tool.

## Test mode and real runs

Automated tests use the backend's internal deterministic model adapter at the network boundary while still executing real Python tools. The local database tests use a temporary directory. The student web app offers only real runs. A simulated response is not evidence of real model quality.

A representative real-model verification must state the model, the samples, the number of calls and the checking criteria, and its results are reported separately. While the backend is running, `scripts/run_live.py <lesson slug> [exercise id] --url <address>` runs an exercise for real and prints an event summary (this incurs model usage). The model finishing, the HTTP request succeeding, the tool executing and the task passing acceptance are different conclusions. Run traces and screenshots are local diagnostic material and are saved in the ignored `.runtime` directory; the SQLite learning memory is not committed to the repository either.
