# Contributing to Agent Learning Studio

**English** · [简体中文](CONTRIBUTING.zh-CN.md)

Thanks for your interest in improving Agent Learning Studio. New lessons, clearer prose, bug fixes and translations are all welcome.

This guide is a short English summary. The authoritative project rules live in [AGENTS.md](AGENTS.md) (in Chinese) and [docs/architecture/](docs/architecture/). The architecture docs have English translations; the Chinese versions are authoritative. See the [documentation index](docs/README.md) for what exists in which language. If this file and AGENTS.md disagree, AGENTS.md wins.

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md). To report a security issue, see [SECURITY.md](SECURITY.md) — please don't open a public issue for it.

## What the project is

A local, visual course for programmers who want to understand how LLM agents work. Each lesson follows **concept → minimal implementation → run evidence → experiment → self-check**. Learners hand-write the agent loop in plain Python first, then move on to context and memory, reliable tools, reasoning and control patterns, RAG, LangChain/LangGraph, evaluation and observability, multi-agent systems and MCP.

The platform puts lesson text, real source code, full model requests and responses, tool execution and event replay side by side. Model access is provider-agnostic: Alibaba Bailian goes through a hand-written raw HTTP path; other providers go through LiteLLM.

## Red lines

Each of these is guarded by tests or validators. If your change needs to break one, open an issue and discuss it with the maintainers first.

1. **Run data comes only from real events.** Never fake or simulate run results for effect. Teaching illustrations must use `provenance=illustration`, pass the contract in `server/illustrations.py`, and are labelled "illustration, not a run record" in the UI.
2. **Replay is read-only.** Replay reads recorded events only; it never calls the model or re-executes tools.
3. **SDK data is never presented as raw HTTP.** Requests and responses standardized by an SDK (LiteLLM) are labelled as such, never as raw HTTP payloads.
4. **Secrets stay in the backend.** Never commit `local_config.py`. Never write keys into run records, logs, commit messages or browser storage.
5. **Offline tests and real-model verification are reported separately.** Automated tests use deterministic model data but must execute the real Python tools. Fixtures (`lessons/*/fixtures.py`) exist only for tests — the web UI has no simulated mode. Report real-model verification separately, with the model, samples and number of calls. Don't claim verification you didn't do.
6. **Lessons start as `planned`.** A lesson is registered in `curriculum/catalog.json` as `planned` and must pass validation as a draft. Only switch it to `available` after implementation, tests and teaching review are complete.
7. **Tests stay green.** Existing tests must keep passing, and changed behavior needs new tests. The frontend selector baseline and the hard-coded Chinese baseline may only decrease.
8. **Check licenses before reuse.** Before reusing text or code from a reference tutorial or upstream project, check its license, keep the attribution and record it in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Setup

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22.12+ and npm.

```bash
uv run lab.py                     # install dependencies, build the UI when needed, start http://127.0.0.1:8765
npm --prefix frontend run dev     # optional: Vite dev server, proxies /api to 8765
```

`uv run lab.py` is the same on Windows (PowerShell), macOS and Linux. For the optional dev server on Windows, use `npm.cmd`.

You don't need a model API key to run the tests or validators. To try lessons in the browser, configure a provider as described in the README. Copy `local_config.example.py` to `local_config.py` for Bailian; that file is git-ignored.

## Checks

Run from the repository root. One command runs everything CI checks except the browser tests:

```bash
uv run lab.py check
```

The individual commands, the same ones CI runs (see [.github/workflows/ci.yml](.github/workflows/ci.yml)):

```bash
# Python
uv run python -m unittest discover -s tests         # all Python tests, incl. every lesson's test_lesson.py
uv run python scripts/validate_lessons.py           # manifests, content, glossary, wording, recordings, translation overlays
uv run python scripts/migrate_content.py --check    # content v2 migration and formatting
uv run python scripts/export_curriculum.py --check  # docs/course-plan.md is in sync with the catalog
uv run python scripts/export_trace_contract.py --check   # frontend mirror of server/envelope.py is in sync
uv run python scripts/export_content_schema.py --check   # exported JSON Schema is in sync with server/content_schema.py
uv run python scripts/realign_notes.py --check      # code-reading notes still point at their anchors
uv run python scripts/term_report.py --lesson <slug> --full   # terms, code notes and wording issues for one lesson

# Frontend
npm --prefix frontend run build
npm --prefix frontend run test          # vitest, using frontend/vitest.config.ts
npm --prefix frontend run i18n:check
```

When you change generated sources, regenerate instead of editing by hand:

| You changed | Run |
| --- | --- |
| `curriculum/catalog.json`, lesson section titles/first sentences, `lesson.json`, glossary | `scripts/export_curriculum.py` |
| `server/envelope.py` | `scripts/export_trace_contract.py` |
| `server/content_schema.py` | `scripts/export_content_schema.py`, then `npm --prefix frontend run content:types` |
| Lesson source moved under its code-reading notes | `scripts/realign_notes.py` |

### Browser tests

Playwright uses the system Chrome (`channel: 'chrome'`) and runs serially because the backend allows one run at a time.

1. Build the frontend and start the backend.
2. In `frontend/`, run `npx playwright test`.

Set `AGENT_LAB_URL` to test another port. If you're running checks in an automated agent, start a separate server instead of taking over someone's 8765 instance:

```bash
uv run uvicorn server.app:app --host 127.0.0.1 --port 8790
AGENT_LAB_URL=http://127.0.0.1:8790 npx playwright test   # in frontend/
```

### Real-model runs

`scripts/run_live.py <slug> [exercise] --url http://127.0.0.1:8765` runs exercises against a real model and prints an event summary. It uses your provider quota. Report its results separately from offline test results.

## Adding a lesson

The full guide is [docs/architecture/adding-lessons.en.md](docs/architecture/adding-lessons.en.md). In short:

1. Register the lesson in `curriculum/catalog.json` with status `planned`, then run `scripts/export_curriculum.py`.
2. Scaffold it: `uv run python scripts/new_lesson.py --id <slug> --dry-run` to preview, then without `--dry-run`. Add `--kind custom` for flows that need their own runner.
3. Implement it in plain Python without frameworks. Add `fixtures.py` (deterministic responses, for tests only) and behavior tests in `test_lesson.py`: real tool execution, error paths, stop conditions, input validation.
4. Write `content.json` following the content v2 schema and the pacing rules in the guide: one topic per lesson, at most five new concepts, anchored code-reading notes, and `{{lesson:<slug>}}` instead of hard-coded lesson numbers.
5. Validate with `validate_lessons.py`, `term_report.py --lesson <slug> --full`, `migrate_content.py --check` and the full Python test suite.
6. After review, switch the status to `available`, regenerate the syllabus, run each exercise once against a real model and check the replay.
7. Record any references you drew on in [docs/architecture/reference-study.md](docs/architecture/reference-study.md) (pinned version, scope, license).

Terminology and the unified wording table are in [docs/architecture/terminology.en.md](docs/architecture/terminology.en.md).

## Translations

Chinese is the source language. Other languages are overlay files keyed by stable IDs (`content.<lang>.json`, `lesson.<lang>.json`, `catalog.<lang>.json`, …). Fact fields can't be overridden, and a translation goes stale — falling back to the source — when the Chinese source changes.

Use `scripts/translation_kit.py`. Targets are `lesson:<slug>`, `onboarding`, `catalog`, `glossary` and `manifest:<slug>`:

```bash
uv run python scripts/translation_kit.py status --locale en                              # coverage and stale entries per target
uv run python scripts/translation_kit.py export catalog --locale en -o todo.json         # missing or stale entries; --all for everything
uv run python scripts/translation_kit.py apply catalog --locale en -i done.json --check  # validate only
uv run python scripts/translation_kit.py apply catalog --locale en -i done.json          # merge and write back
```

`apply` rejects untranslatable paths and translations whose placeholders (`{{...}}`) or inline code (backticks) differ from the source. In English text, use the glossary's `en` term names, sentence-case titles, and keep code names, event names and field names unchanged. `validate_lessons.py` also checks English text: no Chinese outside a documented allowlist, "not reported" (never "unknown") for usage the provider did not report, and English runtime literals quoted directly rather than as `"中文" ("gloss")`. The full checklist and style guide are in [Localizing a lesson](docs/architecture/localizing-lessons.en.md).

UI strings live only in `frontend/src/i18n/locales/<lang>/*.json` — don't hard-code text in components. When you add or change a UI string, update every locale and run `npm --prefix frontend run i18n:check`.

## Conventions

- **Python:** 4-space indentation, `snake_case`. Validate inputs with Pydantic (lesson inputs extend `LessonInputs`). Tool failures return structured errors (`ok=false`, `error_type`, `error`). Don't fail silently.
- **TypeScript/CSS:** 2-space indentation, PascalCase components, `useSomething` hooks. Run Prettier only on files you changed, and keep each file's existing line endings (some files are CRLF). See [.editorconfig](.editorconfig).
- **Browser tests:** locate elements by role, `data-testid` and the text keys in `e2e/i18n.ts` — no CSS class selectors, no hard-coded Chinese.
- **Lesson events:** custom events always use the `lesson.` prefix; reuse existing event families when they fit.

## Commit messages

Use a type prefix: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.

The project convention is Chinese titles, for example `feat: 新课“文本动作与原生工具调用”`. English titles are accepted from external contributors, for example `fix: wrap replay toolbar on narrow screens`.

Keep each commit to one change. Separate lesson content, platform code and docs where you can.

## Pull requests

Your PR description should cover:

- **Behavior change** — what changes for learners or contributors.
- **Verification** — the commands you ran and their pass counts.
- **Offline vs real model** — which parts were only verified offline and which were verified against a real model (model, samples, number of calls).
- **Screenshots** for UI changes.
- **Translations** — UI strings and course overlays updated for both `zh-CN` and `en`, or a note on what is left stale.

Never commit `.runtime/`, `local_config.py`, `frontend/dist/` or `node_modules/`.
