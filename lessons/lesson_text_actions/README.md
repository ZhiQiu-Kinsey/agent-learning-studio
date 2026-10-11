# Text actions and native tool calling (`text-actions`)

English · [简体中文](README.zh-CN.md)

One question (look up a student's latest quiz score and decide whether it is a pass), done three ways. This lesson needs a real model connection.

| Preset | Request | Where the action is written | What the program does |
| --- | --- | --- | --- |
| Text protocol, with stop | `stop: ["Observation:"]` | content text | Parses Action / Action Input with a regular expression, runs the tool, pastes the result back as `Observation:` |
| Text protocol, without stop | no stop | content text | Same; an Observation the model writes itself is cut off and recorded as `lesson.fabricated_observation`, and never enters the context |
| Native tool calling | `tools` parameter | `tool_calls` field | Pairs results by `tool_call_id` and returns them in tool messages |
| Without stop, a failing student | no stop | content text | The real score is below the pass mark, so an invented conclusion visibly contradicts the real result |

Every text output is recorded as `lesson.parse` (raw text, parse result, finish_reason). The parser only uses `raw_decode` to read the JSON at the start of Action Input; any other format error is recorded as a failure and the run stops, with no guessed repair. The tool `lookup_quiz_score` reads the local score table in `runtime.py`, whose numbers the model cannot guess.

Whether a model invents an Observation without stop depends on the model and on this particular sample; this run's record is what counts. `fixtures.py` serves automated tests only; the "invented" content in it is written by a script and stands for no real model.

**Run language:** this lesson runs in Chinese and in English. Both system prompts, the question, the tool description and error, the parser errors and the lab report text are in `locales/zh_CN.py` and `locales/en.py`. Thought, Action, Action Input, Observation and Final Answer are the format the parser reads, so they are the same in both languages. The web page picks the run language from the UI language, and every run record states the language it ran in.

The stop-and-parse approach of the text protocol follows Unit 1 of the [Hugging Face Agents Course](https://github.com/huggingface/agents-course) (Apache-2.0), `actions.mdx` and `dummy-agent-library.mdx`. The prompts, parser and experiments are written for this project; the reading scope is in `docs/architecture/reference-study.md`.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_text_actions.test_lesson -v
```
