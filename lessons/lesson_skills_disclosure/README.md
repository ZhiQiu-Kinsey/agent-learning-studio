# Skills and progressive disclosure (`skills-disclosure`)

English · [简体中文](README.zh-CN.md)

The same task, with skills given to the model in two ways; compare the size of the resident context, the triggering, and the prompt tokens of each request. This lesson needs a real model connection.

| Mode | System prompt | Tools | Requests when a skill is needed |
| --- | --- | --- | --- |
| Full injection | Description and body of all four skills (about 6,000 characters in English, 2,000 in Chinese) | None | 1 |
| Catalog + on-demand loading | One line of name and description per skill (about 1,400 characters in English, 480 in Chinese) | `load_skill(name)` | 2 (propose a load, answer with the body) |

The skill files use the SKILL.md format and are per language in `locales/skills/<name>/zh_CN.md` and `en.md`: `name` and `description` between the first two `---` lines, then the body. The four skills (`review-cards`, `error-question`, `unit-test-checklist`, `three-sentence-summary`) are this lesson's own teaching material. `load_skill` reads only skills registered in `SKILL_NAMES`; the name the model writes is only looked up, never joined into an arbitrary path, and a name not in the catalog returns a structured error.

| Preset | Mode | Task | Description of review-cards |
| --- | --- | --- | --- |
| Make review cards: both modes compared | Both | Make review cards (should load review-cards) | Precise |
| Small talk: both modes compared | Both | Small talk (should not load) | Precise |
| Make review cards: precise / vague description | On-demand loading | Make review cards | Precise / "Helps with studying." |
| Review question: precise / vague description | On-demand loading | Review question (should not load, easy to trigger falsely) | Precise / "Helps with studying." |

After every request the runner publishes `lesson.skill_request`: the `prompt_tokens` the provider reported in usage (null when not reported, and the report says "not reported"), which skill bodies were in the messages actually sent, and which skills the response proposed to load. The final `lesson.report` puts the two modes side by side: prompt tokens per request, the total, the loading record, the loading verdict (correct / missed trigger / false trigger / wrong skill loaded) and the format screen. The format screen only counts lines starting with "Q:" and "A:" ("问：" and "答：" in a Chinese run); it does not judge whether the content is right.

Whether the model loads a skill, and which one, depends on the model used and on this particular sample; the record of this run is what counts. "Should it load" is this lesson's judgement for the three tasks. Running both modes makes at most 4 model calls per run; on-demand loading alone makes at most 3. `fixtures.py` serves automated tests only: its missed and false triggers are scripted, its responses carry no usage, and it stands for no real model.

**Run language:** this lesson runs in Chinese and in English. The system prompts, the description and error of `load_skill`, the user messages of the three tasks, the vague description and the lab report texts are in `locales/zh_CN.py` and `locales/en.py`; the skill files are read in the run's language. The web page picks the language from the UI language, and every run record states the language it ran in. The English skills are longer, so prompt tokens cannot be compared across languages.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_skills_disclosure.test_lesson -v
```
