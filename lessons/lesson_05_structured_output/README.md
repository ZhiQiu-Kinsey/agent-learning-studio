# Structured output and business validation (`structured-output`)

English · [简体中文](README.zh-CN.md)

## Running it

Open the lesson on the web page, pick a preset, change the structured inputs if you like, and click Run. The lab report on the right shows the checks, and you can expand the events; replay only reads what was recorded. This lesson needs a configured real model. The presets normal, missing-field and wrong-fact each generate a task card; repair can be switched off. On a failure the lesson sends at most one more request, so a run makes at most two model calls. Every response gets its own report, so you can compare the first draft and the repaired draft in the lab report. The question box holds a learner note that goes into the report; the structured preset decides the actual task.

**Run language:** this lesson runs in Chinese and in English. The system prompt, the user task, the repair request and the report text are in `locales/zh_CN.py` and `locales/en.py`, and the lesson title among the trusted facts follows the run language too; the exercise questions are written per language in `lesson.json`. The web page picks the language from the UI language, and every run record states the language it ran in.

## Reading the source and the lab

In runtime.py, TaskCard validates the fields with Pydantic; inspect_output checks standard JSON, then the schema, then the business facts in trusted_facts. fixtures.py serves automated tests only. Asking the model to make a mistake in round 1 is a teaching injection that a provider may not follow; do not assume a repair happens every time, and go by the actual responses and each check report. Practice in this order: predict the result, run, compare the requests and reports, change the inputs and run again.

Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_05_structured_output.test_lesson -v
```

## Limits and references

This lesson reads no arbitrary external paths and keeps no long-term state. The lesson "Task goals and acceptance" only proves the acceptance logic for a fixed local case; how a real model behaves in this lesson and in "Prompts and tool descriptions" depends on the current provider, and the reports rely only on this run's responses. Source scope and pinned commits: [source record](../../docs/architecture/chapter2-sources.md).
