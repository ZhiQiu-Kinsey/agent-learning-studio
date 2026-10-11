# One model request (`chat-request`)

English · [简体中文](README.zh-CN.md)

**Goal:** send one real model request without tools, and read `model` and `messages` in the request body, then the answer, the finish reason `finish_reason` and the usage `usage` in the response.

This lesson is a custom runner (`runtime.py`) that calls `context.complete` once:

1. `build_request` builds the body: an optional system message, the user question, and an optional `max_tokens`.
2. `context.complete` sends the request; the platform adds `model` and records the request and response unchanged as `request` and `response` events. `send_bailian` in `course/api_client.py` puts the key into the HTTP header, never into the body.
3. `read_reply` takes the answer, finish reason and usage from the response; usage the provider did not report says "not reported".

Exercises:

| Exercise | What changes | What to look at |
| --- | --- | --- |
| `basic` With system prompt | Defaults | The two messages in messages, the answer, usage |
| `no-system` Remove the system prompt | `system_prompt` left empty | messages has only the user message; how prompt tokens change |
| `short-limit` Set a tiny output limit | `max_tokens` set to 16 | Whether `finish_reason` is `length` and the answer is cut off |

Reasoning models (with `reasoning_content` in the response) count their reasoning in `completion_tokens`; some providers also cap reasoning with `max_tokens`, so with a tiny limit content may be empty. The lab report lists reasoning tokens.

**Run language:** this lesson runs in Chinese and in English. Runtime text such as the report labels and what each finish reason means is in `locales/zh_CN.py` and `locales/en.py`; the exercise questions and the default system prompt are written per language in `lesson.json`. The web page picks the language from the UI language, and every run record states the language it ran in.

Open this lesson from the course navigation on the web page to see the source, real run events and replay. Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_chat_request.test_lesson -v
```

`fixtures.py` serves automated tests only; its answer and usage are fixed fake data.
