# Context components and the message protocol (`messages-context`)

English · [简体中文](README.zh-CN.md)

This lesson splits the context of one request into four parts: the system prompt, the earlier conversation, the tool call with its tool result, and this turn's question. One run prepares five contexts, each with one part less than the full context, and asks the same question:

| Variant | Removed part | Sent? |
| --- | --- | --- |
| Full context | nothing | sent |
| Remove the system prompt | the system message | sent |
| Remove the earlier conversation | that user message | sent |
| Remove the tool call and result | the assistant message with tool_calls and its tool message | sent |
| Remove only the tool result | the tool message (the call stays) | blocked by `validate_tool_history` before sending |

This lesson uses the real model you configured and sends 4 requests per run (the blocked variant is not sent), so mind the model cost. The runner really runs the tool `lookup_score` once; the runner writes the assistant message with tool_calls, the model did not propose it, and the event of this call has `origin` set to `course_program`. The report columns "Mentions score", "Mentions review day" and "Has basis line" are a keyword screen; check them against the answer text.

`validate_tool_history(messages, locale)` keeps its name and behavior. The lessons "Context budget and the truncation window" and "Context compression and probe questions" import it, and the first also imports `rejection_status`: only a request-level 4xx counts as the provider rejecting these messages and is recorded as `lesson.provider_error`; timeouts, rate limits, auth failures, connection failures and 5xx are raised as errors. `locale` only decides the language of the error text.

**Run language:** this lesson runs in Chinese and in English. The system prompt, the conversation samples, the variant names and the report text are in `locales/zh_CN.py` and `locales/en.py`; the errors of `validate_tool_history` are in `locales/protocol/`, because other lessons import it. The exercise questions are written per language in `lesson.json`. The review day `free_day` is a code (`mon` … `sun`) that becomes "周四" or "Thursday" in the conversation, depending on the run language. The web page picks the run language from the UI language, and every run record states the language it ran in.

`runtime.py` assembles the messages, runs the protocol check and builds the report; `fixtures.py` serves offline tests only and builds deterministic answers from the messages of each request. The lesson has no simulated fallback for learners.

For the scope of the references, see `docs/architecture/context-state-sources.md`. The walkthroughs on the page are illustrations; the evidence is in request, response, lesson.context and lesson.report.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_07_messages_context.test_lesson tests.test_lessons_context_state -v
```
