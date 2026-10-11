# Memory updates, expiry, and recall scope (`memory-lifecycle`)

English · [简体中文](README.zh-CN.md)

This lesson calls no model. All three exercises run in a throwaway temporary store; real runs and offline test mode take the same code path and never touch the fixed teaching store of "Persistent memory". The store class is `lessons/lesson_10_persistent_memory/store.py`.

| Exercise | What it does | Where to look |
| --- | --- | --- |
| Two writers and a stale write | Connections A and B read the same version; A writes first and succeeds, B writes with the old version and `VersionConflict` rejects it, then B rereads and writes with the new version | `stale_rejected`, `error`, `value_after_reject` of the `conflict_and_update` event |
| Expiry, deletion, and reopen check | Writes a reminder that has already expired: `get` cannot read it but `stored` finds it; after `delete`, a new connection checks again | The `expired` and `deleted` events; set `expires_in_seconds` to a positive number for the "not expired yet" comparison |
| Recall by scope; recalled content is only data | Seeds persistent records and current_task records of two tasks, recalls for task-now, packages as data, ends the task, recalls for task-next | The `recalled`, `packaged` (`sent_to_model` is false) and `task_ended` events |

- Optimistic concurrency control only stops stale writes within one store. The two writers here run one after the other in one process; this does not prove consistency across machines or database replicas.
- Expiry is a read rule, deletion is a storage operation: an expired row stays in the table until it is deleted explicitly. Deletion does not reset the version: the `versions` table records how far each key has counted, so a key recreated after deletion continues counting up, and a writer holding a version read before the deletion is still rejected.
- `instruction_like` is a rough regex screen that misses some cases and flags harmless ones; it is not a security boundary. It knows a few Chinese and English phrasings, whatever the run language. The packaged messages are only shown, not sent; whether a model acts on such data is tested with a real model in the prompt-injection lesson.

**Run language:** this lesson runs in Chinese and in English. The values and sources written to the store, the report labels and the answers built by code are in `locales/zh_CN.py` and `locales/en.py`; the version-conflict error, the reasons recall skips a record and the rules in system come from persistent-memory's `locales/shared/`. The web page picks the language from the UI language, and every run record states the language it ran in.

References and trade-offs: `docs/architecture/budget-memory-sources.md`.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_memory_lifecycle.test_lesson -v
```
