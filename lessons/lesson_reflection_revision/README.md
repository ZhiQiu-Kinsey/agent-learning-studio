# Reflection, review, and bounded revision (`reflection-revision`)

English · [简体中文](README.zh-CN.md)

The task is fixed: write a regular expression that matches a student ID, a lowercase s, a hyphen and four digits, where the first digit cannot be 0. The tests are 9 fixed cases in `runtime.py`, run for real with `re.fullmatch`; the program only compiles the model's string as a regex and never runs code the model wrote. This lesson needs a real model connection.

| Preset | Review source | Limit |
| --- | --- | --- |
| Model self-review drives revision | The model reads the requirement and the regex and outputs pass / revise | 3 |
| Test results drive revision | The failing cases are the review comments | 3 |
| Test-driven, 1 round only | Same as above | 1 |

- Every version of the regex is recorded as `lesson.draft` (with the previous version), every review as `lesson.review` (`source` is `model` or `tests`), every test run as `lesson.tests`.
- Four stop reasons: the review passed, the iteration limit was reached, the revision made no change, the review output had the wrong format.
- After the loop, the final version is always checked against the same cases; the cumulative `total_tokens` adds up only what the provider reported and states how many calls did not report it.

**Run language:** this lesson runs in Chinese and in English. The requirement, the two system prompts, the failing-case comments, the stop reasons and the report text are in `locales/zh_CN.py` and `locales/en.py`; the exercise questions are written per language in `lesson.json`. The 9 cases themselves do not depend on the language. The web page picks the language from the UI language, and every run record states the language it ran in.

Each arm runs once, so a run cannot show whether self-review is reliable in general. `fixtures.py` serves automated tests only; its drafts, self-reviews and usage are scripted.

The idea of self-evaluation and correction follows chapter 09-metacognition of [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) (MIT); the task, tests, review format and stop conditions are written by this project. The papers [Self-Refine](https://arxiv.org/abs/2303.17651v2) and [Reflexion](https://arxiv.org/abs/2303.11366v4) mentioned in the lesson are cited for their findings only; nothing is copied from them.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_reflection_revision.test_lesson -v
```
