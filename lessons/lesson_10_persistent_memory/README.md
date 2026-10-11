# Persistent memory: save, reopen, and recall (`persistent-memory`)

English · [简体中文](README.zh-CN.md)

This lesson writes one explicitly given memory to SQLite, closes the connection, reads it back on a new connection, then puts the recalled memory into one model request as data.

| Exercise | Calls the model | What it does |
| --- | --- | --- |
| Save and reopen the connection | No | Writes namespace / key / value / source, closes the connection, reads back on a new one; checks that another namespace did not change |
| Read-only recovery of the last memory | No | Reads on a `mode=ro` read-only connection; the report checks with `total_changes` that nothing was written |
| Recall, then have the model answer | Yes, once | Recalls the records of `learner_demo` read-only, writes them as JSON into the `<memory>` data block of the user message, system holds only rules; the answer ends a sentence with `[key]` to show what it relied on |
| Ask again in a namespace with no memory | Yes, once | Recalls from `new_learner`, the data block is empty; compare whether the answer has any basis |

The store class is in `store.py`; the lesson "Memory updates, expiry, and recall scope" (`memory-lifecycle`) uses it too and covers the version check, expiry, scope and deletion.

- Real runs read and write `.runtime/persistent-memory.sqlite3`, which the next run can still read. Run "Save and reopen the connection" first, then "Read-only recovery of the last memory" or "Recall, then have the model answer". The writing exercise changes the namespace and key you choose; use teaching data.
- Offline test mode builds the store in a temporary directory and deletes it afterwards; the read-only exercises first get one controlled record whose source is "sample seeded by the offline test".
- `namespace` is a query partition with no authentication; any caller who knows it can read. The database path cannot be set from the web page.
- `fixtures.py` serves automated tests only: it reads the data block in the request and gives a deterministic answer, standing for no real model. Whether a model cites keys as the rules ask is whatever the response of a real run shows.

**Run language:** this lesson runs in Chinese and in English. Report labels, answers built by code and the recall question are in `locales/zh_CN.py` and `locales/en.py`; the errors of `store.py`, the reasons recall skips a record and the rules in system are in `locales/shared/`, because `memory-lifecycle` uses them too. The learner notes and the presets for value and source are written per language in `lesson.json`. The web page picks the language from the UI language, and every run record states the language it ran in. Records written by Chinese and English runs share the same store and are read back unchanged.

References and trade-offs: `docs/architecture/budget-memory-sources.md`. Illustrations are not run records; the events and the report show what was actually read and written.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_10_persistent_memory.test_lesson -v
```
