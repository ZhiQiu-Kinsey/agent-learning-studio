# Multi-turn conversation: the program resends history (`multi-turn-history`)

English · [简体中文](README.zh-CN.md)

**Goal:** ask several turns in a row and compare requests with and without the previous turn's messages, to see that the model does not remember the last turn on its own: a multi-turn conversation works because the program sends the message history again.

This lesson is a custom runner (`runtime.py`). `run` keeps the message history in a Python list, `history`:

1. Each turn first appends that turn's user question to `history`.
2. The `history` input decides what to send: `full` sends the whole history, `latest_only` sends only system and this turn's question.
3. `context.complete` sends the request, then the answer is appended to `history` as an assistant message.

Exercises:

| Exercise | Settings | What to look at |
| --- | --- | --- |
| `with-history` Ask a follow-up with history | `full`, 2 turns | The four messages of the turn 2 request; whether the answer has the cat's name |
| `without-history` Ask a follow-up without history | `latest_only`, 2 turns | The turn 2 request has only two messages; turn 1 is identical to the other arm |
| `three-turns` Three-turn conversation | `full`, 3 turns | How `prompt_tokens` grows turn by turn |

The lab report lists the messages sent, prompt tokens and completion tokens of each turn; usage the provider did not report says "not reported".

**Run language:** this lesson runs in Chinese and in English. The system prompt, the three questions and the lab report texts are in `locales/zh_CN.py` and `locales/en.py`; the exercise descriptions are written per language in `lesson.json`. The web page picks the run language from the UI language, and every run record states the language it ran in.

Open this lesson from the course navigation on the web page to see the source, real run events and replay. Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_multi_turn_history.test_lesson -v
```

`fixtures.py` serves automated tests only; its answers and usage are fake data.
