# Prompts and tool descriptions (`prompt-experiments`)

English · [简体中文](README.zh-CN.md)

## Running it

Open the lesson on the web page, pick a preset and run it. The lab report on the right shows the checks, and you can expand the events to see the raw requests and responses; replay only reads what was recorded. This lesson needs a real model connection. Every preset fixes the user task, the model and temperature=0.

| Preset | Variable changed | Model calls | Tools executed? |
| --- | --- | --- | --- |
| Tool description: vague vs. clear | function.description | 2 | No, the proposals are only screened |
| Process rule: answer and check | system rule | 2 | No tools |
| Failure boundary: missing addend | system rule | 2 | No tools |
| Tool description matrix | description: blank / good / misleading, each with a sum probe and a concatenation probe | 6 | Yes, add_numbers proposals with a valid name and arguments |

The question box holds a learner note: it goes into the report and does not change the fixed task.

**Run language:** this lesson runs in Chinese and in English. The paired tasks, the tool descriptions, the matrix probes, the screening rules and the report text are in `locales/zh_CN.py` and `locales/en.py`; the exercise questions and the sample label are written per language in `lesson.json`. The web page picks the language from the UI language, and every run record states the language it ran in.

## Reading the source

`pair_tasks` in the message catalog fixes the paired conditions, and `descriptions` and `probes` define the matrix; `MATRIX_GROUPS` and `PROBE_EXPECTED` in `runtime.py` give the matrix rows and columns and the call each probe expects. The paired experiments use structure or keyword screening; a hit still means reading the raw response yourself. The matrix experiment hands the calls the model proposed to the real `add_numbers` through `context.execute_proposal`, so the events record the call exactly as the model gave it; the report puts the model's proposal next to the code's return value, and the misleading description deliberately disagrees with the implementation.

Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_06_prompt_experiments.test_lesson -v
```

## Limits and references

Each cell and each pair runs only once. That is not enough to prove that one wording is better in general; you need more samples and repeated runs. `fixtures.py`, used by the offline tests, serves automated tests only and does not stand for any real model. Source scope and pinned commits: [source record](../../docs/architecture/chapter2-sources.md).
