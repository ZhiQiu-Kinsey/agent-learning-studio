# Sampling and uncertainty (`sampling-variance`)

English · [简体中文](README.zh-CN.md)

**Goal:** send the same request 5 times unchanged, compare the answers at `temperature` 0 and 1.3, and see that model output comes from sampling. That is why one run proves nothing and why each arm of a controlled experiment has to be run several times.

This lesson is a custom runner (`runtime.py`):

1. The body is built once: the system rule, the user question and `temperature`.
2. The same body is sent through `context.complete` several times (5 by default; `max_rounds` in `lesson.json` is 5).
3. `count_distinct` trims leading and trailing whitespace and compares character by character to count the distinct answers; the lab report lists every answer and the usage totals.

| Exercise | Setting |
| --- | --- |
| `low-temp` | `temperature` 0, sent 5 times |
| `high-temp` | `temperature` 1.3, sent 5 times |

Each exercise calls the model 5 times. If the provider does not report usage for one of the calls, the total says "not reported".

**Run language:** this lesson runs in Chinese and in English. Runtime text such as the system prompt and the report labels is in `locales/zh_CN.py` and `locales/en.py`; the exercise question is written per language in `lesson.json`. The web page picks the language from the UI language, and every run record states the language it ran in.

Open this lesson from the course navigation on the web page to see the source, real run events and replay. Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_sampling_variance.test_lesson -v
```

`fixtures.py` serves automated tests only; its answers are fixed names in rotation and do not show how a real model varies.
