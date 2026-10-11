# Localizing a lesson: bilingual runtime and English overlay

**English** · [简体中文](localizing-lessons.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

A lesson that supports both Chinese and English needs two things: runtime text (what is sent to the model and written into events) lives per run language in the `locales/` message catalog, and the English teaching content lives in the translation overlays `content.en.json` and `lesson.en.json`.
The mechanism and conventions are in the "Multilingual runtime" section of [Adding lessons](adding-lessons.en.md). This document is the per-lesson checklist. Use it when:

- a new lesson has only a Chinese runtime and needs English;
- you change the runtime text of an existing lesson (prompts, reports, tool descriptions);
- a further run language is added later — the steps are the same.

All 24 current lessons are already bilingual. When in doubt, copy the reference lessons: **`chat-request`** (custom runner) and **`tool-selection`** (native runner).

## Definition of done

- An English run of every exercise contains **no Chinese anywhere**: request bodies, tool results, `lesson.*` reports, answers and `run_start` all count.
- A Chinese run behaves exactly as before.
- The Code scene shows the message catalog of the UI language.

All of these must pass:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.<lesson dir>.test_lesson -v
.\.venv\Scripts\python.exe -m unittest discover -s tests          # includes test_runtime_locales, test_lesson_experiments (both locales), test_english_text
.\.venv\Scripts\python.exe scripts/validate_lessons.py
.\.venv\Scripts\python.exe scripts/term_report.py --lesson <slug> --full
.\.venv\Scripts\python.exe scripts/migrate_content.py --check
.\.venv\Scripts\python.exe scripts/realign_notes.py --check
.\.venv\Scripts\python.exe scripts/export_curriculum.py --check
.\.venv\Scripts\python.exe scripts/translation_kit.py status --locale en   # this lesson: complete, 0 stale
.\.venv\Scripts\python.exe scripts/cjk_baseline.py                        # then --check; the count for this lesson may only drop
```

No real model is needed for this. If you start a server, use your own port (for example 8791), not the 8765 instance someone is using. Keep each file's line endings (`git ls-files --eol` shows them).

## File layout

```text
lessons/<lesson dir>/locales/__init__.py   @dataclass(frozen=True) class Texts: one field per message
                                           texts_for = catalog(__name__, Texts)   # from course.i18n
lessons/<lesson dir>/locales/zh_CN.py      TEXTS = Texts(...)   # source language, today's Chinese text verbatim
lessons/<lesson dir>/locales/en.py         TEXTS = Texts(...)   # English
lessons/<lesson dir>/locales/<part>/...    a separate catalog for a module other lessons import (see tool-selection's locales/tools/)
lessons/<lesson dir>/locales/<data>/zh_CN.md, en.md   per-language data files read at run time (load with course.i18n.localized_file)
lessons/<lesson dir>/README.md             English, links to README.zh-CN.md
lessons/<lesson dir>/README.zh-CN.md       Chinese, links to README.md
```

Module docstrings of catalogs are English (`"""<slug> runtime text: English."""`).

## Checklist

1. **Inventory.** List every string that reaches the model or an event: system prompts, tool descriptions (parameter descriptions too), tool error messages, preset questions and inputs, report titles/summaries/labels/values/table columns, task cards, reminders, `lesson.*` titles, answers built by code, and errors raised into the run (a `ValueError("…")` that ends up in an `error` event or a tool result). `scripts/cjk_baseline.py` plus a search for Chinese in `runtime.py`, `tools.py`, `store.py` and `fixtures.py` finds them.
2. **Create the catalog.** Field names describe the message (`report_title`, `label_prompt_tokens`, `not_a_number`), not its position. Templates use named placeholders: `"Round {round} of {limit}"` with `.format(round=…, limit=…)`; never build a sentence with `+`. Values may be `str`, `tuple[str, ...]` or `dict[str, str]` (for example code → meaning). Keep the Chinese byte-identical to today's literal so Chinese runs do not change.
3. **Rewrite the code.** Take `t = texts_for(context.locale)` at the top of `run`, then use `t.<field>`. Do not compute language-dependent module constants at import time (`DEFAULT_QUESTION = "…"` becomes `t.default_question` inside `run`). Pass `t` (or `locale`) explicitly into helpers; no globals, no context variables.
   - **Native lessons:** `main.py` exports `setup(locale) -> AgentSetup(system_prompt, tools, available_tools)`; `main(locale=None)` reads the language with `cli_locale()` and calls `run_cli(setup(locale), title=t.cli_title, examples=t.cli_examples, max_tool_rounds=…, locale=locale)`. `run_native` only knows `setup`.
   - **Tools:** `tool_definitions(locale)` builds the JSON Schema list (tool names and parameter names are code, identical in every language; descriptions come from the catalog). A tool that raises messages takes the catalog as a **positional-only first parameter** — `def divide(t, /, a, b)` — and `available_tools(locale)` binds it with `functools.partial(divide, texts_for(locale))`. The model's arguments always arrive by name, so they can never replace `t`; extra arguments stay a `TypeError`.
   - **Custom runners that send tools** export or import `tool_definitions(locale)` so the Code scene can attach evidence links to the tool functions (`tool-proposals` imports it from `tools.py`).
   - **Platform methods:** `context.call_tool`, `context.execute_proposal`, `context.submit_call` and `context.run_native` already pass `context.locale` to `course/`. If you call `course.runner.execute_tool` directly, pass the locale yourself.
4. **`lesson.json`.** Add `"locales": ["zh-CN", "en"]` to `runtime`. Every natural-language `question`, `inputs` value and `input_defaults` value becomes `{"zh-CN": "…", "en": "…"}`; numbers, booleans and code values stay scalar (a plain string containing Chinese is rejected in a bilingual lesson). Add the catalog files to `sources` after the annotated code files and before `fixtures.py` (the Code scene opens files in this order, and the phone tests click the second file), each with `"locale"` (`zh_CN.py` → `"zh-CN"`, `en.py` → `"en"`). For every `locales/` directory you list, list every runtime locale; the `__init__.py` holding `Texts` is optional (the reference lessons leave it out). Exercise titles are still translated in `lesson.en.json`.
5. **`INPUT_MODEL`.** No Chinese defaults: a natural-language field gets no default (the preset in `input_defaults` supplies it per language) or a language-neutral one. `Literal` options are codes (`"mon"`, not `"周一"`); their labels go in `content.json` `lab.inputs[].options` and are translated by the overlay. `test_runtime_locales` checks the input schema of English lessons for Chinese.
6. **Fixtures.** `create_completion(exercise_id, inputs=None, locale="zh-CN")`, with deterministic answers per language (a `{"zh-CN": …, "en": …}` dict in `fixtures.py`; fixture data never goes into the learner-facing catalog). Use `server.offline.offline_marker(locale)` for the leading marker and `result_answer(results, locale)` for tool-result summaries. Tools still really run.
7. **Lesson tests (`test_lesson.py`).** Keep every Chinese assertion; where the text differs, add the same checks for `locale="en"`. Construct `RunContext(..., locale=locale)`. Assert on catalog values (`texts_for("en").report_title`) rather than retyping long strings. Docstrings and comments in lesson code are English.
8. **Comments and docstrings.** English in lesson Python files and in `course/`; `server/`, `scripts/` and `tests/` stay Chinese. Explain why, not what.
9. **Chinese content (`content.json`).**
   - Quote runtime text exactly as the Chinese catalog has it.
   - Code names you renamed (`TOOLS` → `tool_definitions`, `SYSTEM_PROMPT` → `t.system_prompt` in a catalog) must be updated in the prose, in `code_notes` (≤ 60 characters; the name must exist in the lesson's sources) and in concept-card `token`s.
   - Walkthrough `code` snippets are fact fields (no overlay): make them language-neutral (`"content": "……"`, English comments).
   - Re-anchor the code-reading notes: `python scripts/realign_notes.py <lesson dir>`. It refuses blocks whose anchors vanished; fix those by hand (new `line` and `anchor`). Then check each block's `start`/`end` by eye: when the first line of a block was rewritten, realign may move `start` into the previous function.
   - To annotate a prompt line by line, make an `annotated-source` block on `locales/zh_CN.py` (source language only, explicit `start`/`end`, every line inside a `TEXTS` field). In the English catalog each covered field must keep the **same number of lines** (one sentence per line in both); the platform maps the block to `en.py` by field and line offset. The density rules apply to such blocks too.
   - Usage the provider did not report is "未报告"; "未知" is only for values that truly cannot be known (the validator rejects "用量未知" and similar; see [Terms and code names](terminology.en.md)).
10. **English overlay (`content.en.json`).**
    - Export the entries to translate: `translation_kit.py export lesson:<slug> --locale en -o todo.json`; write the English; run `apply … --check`, then `apply`.
    - Quote the **English** runtime literal exactly (`"not reported"`, the English system prompt), never the old `"中文" ("gloss")` form; `validate_lessons` rejects it.
    - Paths keyed by a code name (`code_notes.<name>.note`) change when the name changes: **delete the old key** from `content.en.json` first, otherwise the whole overlay is rejected and the lesson falls back to Chinese.
    - Follow "English style" below.
11. **README.** English `README.md` plus Chinese `README.zh-CN.md`, linked to each other (`English · [简体中文](README.zh-CN.md)`). Mention the run language, and `--locale en` for native lessons.
12. **Baseline.** Run `python scripts/cjk_baseline.py` to tighten `tests/baselines/python-cjk.json` (it may only go down; `locales/zh_CN.py` and `test_*.py` are exempt).

## Pitfalls we hit

- **Values the OS localizes.** On a Chinese Windows, `datetime.tzname()` returns "中国标准时间". Prefer language-neutral data (`tool-selection` now returns an offset such as `"UTC+08:00"`). The no-Chinese test catches this kind of leak; fix the data, do not mock it away.
- **Shared modules.** `lesson_07_messages_context/runtime.py` is imported by `context-budget` and `context-compaction`; `store.py` in `lesson_10_persistent_memory` by `memory-lifecycle`; `lesson_01_tool_selection/tools.py` by `tool-proposals` and `dependent-calls`. Give the shared module its own catalog (`locales/<part>/`) and a `locale` parameter, and keep every importing lesson green (its `sources` must list the shared catalog file for each of its runtime locales).
- **Fixtures importing runner constants** (`prompt-experiments`, `orchestrator-evaluator`, `workflow-patterns`, `context-compaction`): import the catalog instead, or pass the locale through.
- **Renaming a `code_notes` name** silently invalidates the overlay key (see step 10).
- **`tests/test_code_reading.py`** asserts "New in this lesson" for some lessons. Catalog fields take part as `t.<field>` (compared on the Chinese catalog, so both languages agree); update the expectations deliberately.
- **Observation-point selectors** must not depend on text values: `test_lesson_experiments` runs every arm in both languages.
- **Report labels used as keys in tests:** map labels back to catalog fields (see `metrics()` in `lessons/lesson_chat_request/test_lesson.py`) so one assertion covers both languages.
- **Error messages raised inside tools** become tool results the model reads: they are runtime text, not developer errors.
- **Markdown data files** (the `prompt-caching` handbook, the `skills-disclosure` `SKILL.md` files) are sent to the model: put them in `locales/<name>/zh_CN.md` and `en.md`, register both with `locale`, and read them with `localized_file(directory, context.locale, ".md")`.

## Do not

- Translate tool names, parameter names, event types, JSON keys, `lesson.*` event names or `Literal` codes.
- Put fixture answers into `locales/`.
- Change what a Chinese run sends. The only exception is replacing OS- or machine-dependent wording with language-neutral data; say so in the PR.
- Change `server/`, `course/` or the frontend in the same change; propose platform changes separately.

## English style

The readers are programmers learning how agents work: plain, direct, technical English (American spelling), short sentences, conclusion first.

- Translate meaning, not Chinese word order. No marketing words ("powerful", "seamless", "delve", "crucial", "it's worth noting", "in summary").
- Keep every honesty distinction in the source: "the run finished", "the request succeeded", "the tool executed" and "the task passed acceptance" are different claims; "未报告" is "not reported" and "未知" is "unknown". Never soften or strengthen a claim.
- Titles and short UI labels use sentence case, not Title Case. Replace full-width punctuation with English punctuation. "第 2 轮" is "round 2", "第 3 行" is "line 3"; lesson references stay `{{lesson:<slug>}}`.
- Keep byte-identical: `{{…}}` placeholders, every backtick span, code names, event types, field names, file names, JSON keys, model and provider names, and labels that are already English in the source (such as `"01 / REQUEST"`). `translation_kit.py apply` rejects translations whose placeholders or inline code differ.
- Use the glossary's `en` name for each course term (`curriculum/glossary.json`), consistently. Where the Chinese introducing lesson writes "中文（English）", write the term once, lowercase in running text unless it is a proper noun or acronym. Never put both languages side by side in English text.
- Translate a given exercise, experiment or arm title the same way everywhere in a file; exercise titles follow `lesson.en.json`.
- English text must not contain Chinese. Anything that has to stay (the Chinese title of a reference book, a Chinese example in a tokenization explanation) goes into `ENGLISH_CJK_ALLOWED` in `server/vocabulary.py` with a reason; see section 5 of [Terms and code names](terminology.en.md).

Fixed UI vocabulary — the English must match the UI exactly:

| Chinese | English |
| --- | --- |
| 理解 / 读码 / 实验 / 自检 / 回顾 (scenes) | Understand / Code / Lab / Check / Review |
| 开始之前 | Before you start |
| 课程地图 / 完整课程表 | Curriculum map / Full syllabus |
| 实验台 / 运行观察台 | lab bench / run console |
| 运行记录 / 回放 | run record / replay |
| 舞台 / 胶片 / 时间线 | stage / film strip / timeline |
| 工具卡片 | tool card |
| 观察点 / 导览 | observation point / guided tour |
| 对照组, 实验组 | arm (for example "arm A") |
| 假设 / 预测 | hypothesis / prediction |
| 微型自测 | quick check |
| 实验报告 | lab report |
| 本课新增 | New in this lesson |
| 教学示意 · 非运行记录 | Illustration · not a run record |
| 深入一点 | Deep dive |
| 练习 / 实验 / 预设 | exercise / experiment / preset |
| 服务商 / 用量 | provider / usage |
| 标准化请求/响应 | SDK-standardized request/response |
| 原生 HTTP | raw HTTP |
| 百炼 | Bailian |
| 验收 | acceptance check / acceptance |
| 平台代码 / 课程代码 | platform code / lesson code |
| 测试夹具 | test fixture |
| 已实现 / 计划中 | available / planned |

Don't guess silently when you are unsure of a translation: list it in the PR description for the reviewer.
