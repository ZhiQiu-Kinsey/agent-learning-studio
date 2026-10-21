# File tools, edit strategies and change evidence (`file-edit-evidence`)

English · [简体中文](README.zh-CN.md)

A coding agent that edits files through `bash -c "sed -i ..."` leaves you guessing afterwards: which file did that command touch, what did it become, did it leave the workspace? This lesson replaces Bash with dedicated file tools and answers three questions: how to compare the ways a model can say "change this" (whole-file rewrite, exact replace, line replace), how to prove a change with hashes and a unified diff, and how to refuse a write that rests on a file that has since changed. The model-driven exercises call a model; the "five guards" exercise calls none and runs no command.

## The tools

Each run works in a throwaway copy of `fixture_repo/` (a small shop library: `shop/pricing.py`, `shop/report.py`, and 7 tests of which 2 fail). Every path goes through `Workspace.resolve` from `course/sandbox.py`.

| Tool | What it does | What it refuses |
| --- | --- | --- |
| `read_file` | returns the lines with line numbers (`start_line`, `end_line`, at most 400 lines) and a `version` (first 12 characters of the sha256); remembers what the model has seen | paths outside the workspace, missing, binary, non-UTF-8 or oversized files |
| `write_file` | writes the whole file; creates a new file without a read | an existing file that was never read (`NotReadYet`), read only in part (`PartialRead`), changed since the read (`StaleRead`) |
| `edit_file` | exact replace: `old` must occur exactly once | `OldStringNotFound`, `OldStringNotUnique` (with the lines), an edit that changes nothing (`NoOpEdit`) |
| `edit_lines` | line replace by first and last line number | numbers outside the file (`InvalidRange`), line numbers made void by an earlier write (`LineNumbersStale`) |
| `run_tests` | runs `python -m unittest discover -s tests` through the sandbox runner | without a container: anything the human does not approve |

Writes under `tests/` are always refused (`ProtectedPath`); reading is allowed. After every write the tool compiles Python files (never runs them) and reports a syntax error in the result. Writes are atomic: a temporary file is written and renamed over the target.

## The evidence

Every write-type call leaves one row in the journal (`FileTools.journal`), emitted as a `lesson.file_change` event: tool, path, `ok`, `changed`, `error_type`, `before_sha256`, `after_sha256`, lines added and removed, `syntax_ok` and the unified diff. A refused call leaves a row too, with equal hashes.

At the end of an `edit` run the platform checks the result itself and puts it in `lesson.report` (the lab report):

- `tests_pass`: the platform reruns the tests; if the command did not run (approval rejected) the item has no `passed`, because a command that never ran says nothing about the code;
- `tests_untouched`: no file under `tests/` changed (`Workspace.protected_changes`);
- `scope`: only `shop/pricing.py` changed, and among its top-level names only `discount_rate` and `shipping` changed or vanished (`symbol_changes`);
- `evidence_chain`: `verify_chain` replays the journal against the workspace's own hashes: each row starts where the previous ended and the last ends at the file's hash now.

The model's closing message is quoted in the answer and never trusted. The metrics also count the argument characters of write calls (what was actually sent, refused calls included), the characters of tool results, the model calls, and tokens only as the provider reported them ("not reported" otherwise).

## Not isolated: how the tests run

The only command in this lesson is the fixed test command, but it executes code the model edited. Without a container engine the restricted runner is **not isolated**: it runs on your machine as your user. So every run of it, the model's own `run_tests` and the platform's acceptance run, waits for your approval first (`RunContext.request_approval`; the card shows the command, `isolated: false` and the files changed so far), and the `lesson.sandbox` event, the report and the approval summary say "Not isolated · commands run on your machine". With a container available the runner is used and no per-command approval is asked. Offline test mode always uses the restricted runner, so the tests do not depend on whether the machine has a container engine. Details: `docs/architecture/sandbox.md`.

## Files

| File | Contents |
| --- | --- |
| `file_tools.py` | `FileTools`: the four tools, the guards (`_check_view`), the shared write frame (`_write`), the journal; the error classes |
| `evidence.py` | `unified_diff`, `verify_chain`, `symbol_changes`, `unittest_summary` |
| `runtime.py` | the `edit` scenario (agent loop, sandbox, approval, report) and the `guards` scenario; `run(context)` is the entry point |
| `fixtures.py` | the offline test model and approval policy (tests only; there is no entry for it on the web page) |
| `fixture_repo/` | the repository the model works on |
| `locales/` | prompts, tool descriptions, tool errors, report text, in Chinese and English |
| `test_lesson.py` | behavior tests: real file tools, real hashes and diffs, real `unittest` runs in the temporary workspace |

## Exercises

| Exercise | What it does | Where to look |
| --- | --- | --- |
| Whole-file rewrite: `write_file` | the model gets read, `write_file` and `run_tests` | `lesson.file_change`; the report's argument characters and `scope` |
| Exact replace: `edit_file` | the same task with `edit_file` | a refused `OldStringNotUnique` if it happens; the diff of each edit |
| Line replace: `edit_lines` | the same task with `edit_lines` | `LineNumbersStale` after an edit that changed the number of lines; the extra read |
| Five guards (no model call) | the runner submits flawed calls, declaring the expected outcome first | the report table: expected, actual and "files unchanged" per step; `lesson.external_change` and the broken link in the stale case |

Compare the three strategies on the same task: argument characters, refused calls, model calls, and whether the final hash of `shop/pricing.py` is the same. One run is one sample; run each strategy several times before drawing a conclusion.

## Boundaries

- The scripted offline model makes the same fix three ways, so offline all three end at the same file; with a real model they may differ. Nothing in the lesson text predicts a real result.
- `shop/pricing.py` has 45 lines, which does not show the gap on a large file; the deep dive does the arithmetic for 600 lines.
- Stale-write detection compares the hash when the write starts; a few milliseconds remain between that comparison and the rename. There is no file lock.
- The tools handle UTF-8 text files inside the workspace only. Symbolic links, binary and very large files are only refused.
- A closed hash chain proves what happened, not that the change is right.

**Run language:** this lesson runs in Chinese and in English. Prompts, tool descriptions, tool errors and report text are in `locales/zh_CN.py` and `locales/en.py`; tool names, argument names, event names and error class names are code and the same in both languages.

## How to run

Offline tests (real tools, real hashes, real test runs; the model is scripted test data):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_file_edit_evidence.test_lesson -v
```

The lesson is still `planned` and has only been verified offline; no real model has run it. Once it opens, run it in the web lab, or with `scripts/run_live.py file-edit-evidence <exercise> --ask-approvals` (the model exercises use model quota; the `guards` exercise does not).

References: *Understanding AI Agents in Depth* (深入理解 AI Agent), chapter 4 (dedicated tools against general executors, fidelity of argument passing, security layers of execution tools) and chapter 5 ("file editing tools in a coding agent", with its companion `tools/edit_tool.py`, `read_tool.py` and `write_tool.py`); Learn Claude Code `s02_tool_use`; the Mini-SWE-agent documentation (the Bash-only route, for contrast). The code and experiments were written for this project.
