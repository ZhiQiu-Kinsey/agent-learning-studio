# Prompt caching and the stable prefix (`prompt-caching`)

English · [简体中文](README.zh-CN.md)

Prerequisite: Context budget and the truncation window (`context-budget`). This lesson needs a real model connection.

Ask about the same library handbook (`locales/handbook/en.md`, fictional teaching material, about 8,800 characters in English) several times in a row and see how much of the start the provider reuses. The three arms use exactly the same rules, handbook and questions; only the position of the "dynamic line" (request number and send time) changes:

| Exercise | `layout` | Position of the dynamic line | Model requests |
| --- | --- | --- | --- |
| Dynamic content first | `dynamic_first` | First line of the system prompt | `repeats` (default 4) |
| Stable prefix | `stable_prefix` | End of the last user message | `repeats` |
| Stable prefix + warmup | `warmup` | Same, after one warmup request that asks only for the reply "Read" | 1 + `repeats` |

`repeats` is 3–5; `max_rounds` in `lesson.json` is 6 (warmup + 5 measured requests).

## What each request records

Each request emits one record event: `lesson.cache_hit` when the provider reports a hit (greater than 0), `lesson.cache_miss` when it reports 0, and `lesson.cache_unreported` when the response has no cache field. A record holds:

- `prefix_hash`: all messages before the last one (here: system), serialized with sorted keys, first 12 hex digits of sha256;
- `shared_prefix_chars`: how many characters this request and the previous one share from the start after serialization;
- `input_tokens`, `cached_tokens`, `cache_write_tokens`, `field`, `ratio`: normalized from the response's `usage` by `normalize_cache_usage` in `cache_usage.py`;
- `elapsed_ms`: the runner times around `context.complete`, a few milliseconds more than `duration_ms` of the `response` event because it includes recording the event.

`normalize_cache_usage` reads three shapes (field names checked against each provider's documentation on 2026-10-03):

| Provider / API | Hit field | All input |
| --- | --- | --- |
| OpenAI-compatible endpoints (Bailian included) | `usage.prompt_tokens_details.cached_tokens` | `prompt_tokens` (hits included) |
| DeepSeek's own API | `usage.prompt_cache_hit_tokens` | `prompt_tokens`; without it, hits plus `prompt_cache_miss_tokens` |
| Anthropic | `usage.cache_read_input_tokens` | `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` |

With no cache field, or a value that is not a non-negative integer, `cached_tokens` is `None`, the report says "not reported" and no hit ratio is computed; it is never treated as 0.

## Session tag

The first line of the system prompt (the second line in the dynamic-first arm) is a session tag. With `isolate_run` set to `true` (the default) it is an 8-character hexadecimal string generated for this run: the same within a run, so the prefix holds, and different between runs, so cache left by an earlier run cannot be used and the three arms do not affect each other. Set to `false`, it is fixed to "not isolated", so you can observe reuse across runs; the report's third check points out requests that report a hit although their prefix appears for the first time in this run.

## Run language

This lesson runs in Chinese and in English. The rules, questions, dynamic line, session tag and lab report texts are in `locales/zh_CN.py` and `locales/en.py`; the handbook is per language in `locales/handbook/zh_CN.md` and `en.md`, and a run reads the one in its language. The web page picks the language from the UI language, and every run record states the language it ran in. The two handbooks differ in length, so cached token counts cannot be compared across languages.

## Offline tests

`fixtures.py` serves automated tests only: it remembers the requests of the run and makes up the hit count from "characters identical from the start with an earlier request" (2 characters count as 1 token, rounded down to blocks of 64). The dynamic-first and stable-prefix arms return the OpenAI-compatible format; the "Stable prefix + warmup" arm deliberately returns no cache field, to test "not reported". Tests also switch to the DeepSeek and Anthropic shapes with the `style` parameter. Offline reports say the numbers come from the fixture.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_prompt_caching.test_lesson -v
```

The provider's minimum cacheable length, hit granularity and lifetime are whatever its current documentation and actual responses say; this lesson does not hard-code them.
