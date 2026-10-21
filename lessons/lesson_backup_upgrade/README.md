# Backup, restore and upgrade rollback (`backup-upgrade`)

English · [简体中文](README.zh-CN.md)

**The question of this lesson:** when the data is damaged or an upgrade goes wrong, can you get back? The lesson calls no model. All four exercises work on two real SQLite files in a temporary directory, laid out like your local `.runtime/` (`runs.sqlite3` holds runs, `memory.sqlite3` holds memory), and never read or write your real `.runtime/`. The temporary directory is deleted when the run ends. It follows "Local delivery" (keys and configuration stay in the backend) and "Persistent memory" and "Memory updates, expiry, and recall scope" (reading and writing the memory store).

**Status:** the lesson is still `planned`. Only after implementation, tests and teaching acceptance are done does the status in `curriculum/catalog.json` change to `available`. There is no model call here, so there is no "verified with a real model" item: a real run and offline test mode take the same code path, and pressing "Run" on the web page is a real local run.

## File guide

| File | Content |
| --- | --- |
| `backup.py` | The four ways to copy (page by page, SQLite backup API, `VACUUM INTO`, copy after a stop); building and checking the backup manifest `manifest.json`; restoring into a new directory; `restore_into` for rolling back; `prune` for keeping the last N |
| `migrate.py` | The data migration from v1 to v2: `migrate_memory` rebuilds a table, `migrate_runs` renames, adds a column and backfills; optional transactions; the fault injector `Fault` (raise midway, or silently drop rows) |
| `checks.py` | Checks: `integrity_check`, row rules, the content digest, `service_check` (start the service of a version on the data), the key scan |
| `seed.py` | The teaching data directory and `LiveWriter`, a writer thread that really commits |
| `runtime.py` | The flow of the four exercises; `reports.py` assembles `lesson.report` and the helper events |
| `locales/` | Runtime text, one catalog per language; the teaching data (memory texts, event bodies) lives here too |
| `test_lesson.py` | Behavior tests: real SQLite, a real writer thread, both run languages, the fault matrix |

The code page has three blocks: the copy methods (`backup.py`), the manifest and its check (`backup.py`), and the migration inside a transaction (`migrate.py`).

## The four exercises

| Exercise | What it does | Where to look |
| --- | --- | --- |
| Online backup | Writes 8 runs and 8 memories, lets the writer thread commit 6 more units, backs up with the chosen method while the writer keeps committing in the middle of the copy, then reads both copies back and runs `integrity_check` and the row rules on each | `lesson.backup` (journal mode, the `-wal` file, writes during the copy), the two checks per file in the report |
| Restore drill | Back up, check the manifest, restore into a new directory, accept by reading the data the way the service does; the backup scope can change, one byte can be flipped or the file truncated, and the manifest check can be turned off | `lesson.verify`, `lesson.restore`, and `damage_caught`, `digest_matches`, `no_secrets` in the report |
| Upgrade and rollback | Migrates `memory.sqlite3`, then `runs.sqlite3`; the program causes the chosen failure; the way back follows the chosen safeguard; the service and the data are checked at the end | `lesson.fault` (origin `fault_injection`), `lesson.migration`, `lesson.rollback`, and `service_available`, `data_unchanged` in the report |
| Keeping the last N | Makes 6 backups, damages the newest few, prunes by policy, then restores from what is left | `lesson.retention`, and `restorable_after_prune`, `runs_lost` in the report |

Each exercise above has preset variants in `lesson.json`, one per arm of the experiments (offline mode only accepts the structured inputs of the exercise's own preset): online backup has `online-backup` (copy while writing), `online-backup-api`, `online-vacuum-into` and `online-cold-copy`; the restore drill has `restore-drill` (clean), `restore-bit-flip-verified`, `restore-bit-flip-skipped` and `restore-whole-directory`; upgrade and rollback has `upgrade-rollback` (backup plus transactions, second file fails), `upgrade-no-safeguard`, `upgrade-transaction-first-file`, `upgrade-transaction-second-file` and `upgrade-transaction-bad-result`; keeping the last N has `retention` (newest N plus the newest verified one) and `retention-newest-only`. The retention pair is compared inside the restore-drill experiment.

How to read the results:

- Online backup with "Copy the file while it is written": the `runs.sqlite3` copy has `integrity_check` ok but is missing the 6 runs committed before the backup began (they are still in `-wal`); the `memory.sqlite3` copy is torn and its two tables disagree. The copies from the backup API, `VACUUM INTO` and copying after a stop pass both checks.
- Restore drill with "flip one byte": the manifest check fails and the restore is refused; turn the check off and `integrity_check` passes and memory is still recalled, and only the content digest item fails.
- Upgrade and rollback: with transactions alone, a failure in the first file rolls back completely, while a failure in the second file or a migration that "succeeds but drops rows" cannot be undone; backup plus transaction returns to before the upgrade in all three cases, and the service and the data are checked.
- Keeping the last N: keeping only the newest N cannot restore when the newest few are damaged; adding the newest one that verifies can restore, at the cost of a few runs compared with the newest data.

## Honesty notes

- The databases, the writer thread, the copies and the checks are all real; only the faults are made by the program: the flipped byte, the truncation, the exception raised inside the migration and the dropped rows. Each is marked with the origin `fault_injection` in a `lesson.fault` or `lesson.migration` event, and none of them is behavior of a backup tool or of SQLite.
- The default write pacing of online backup is "writes and copy steps alternate": after every page copied the writer thread commits one unit. The result is the same every time and the writes are real commits, but the timing of the overlap is arranged by us. Switch the pacing to "free-running" and the writer thread runs on its own, and the result of a direct copy may differ per run. Tests assert concrete results only for the alternating pacing and only invariants for free-running.
- The key scan only recognizes one fake marker the lesson plants in the directory (`sk-demo-canary-…`, not a real key) and strings starting with `sk-`; it cannot prove the backup holds nothing else sensitive.
- Not covered: off-site backups, backup encryption, behavior on power loss, writes between the upgrade and the rollback, and rolling back the program version (only the data is rolled back).
- Sources of facts: four SQLite documentation pages (the online backup API, `VACUUM INTO`, write-ahead logging, how to corrupt a database); the deployment and memory lessons of Microsoft AI Agents for Beginners; chapters 3 (knowledge updates and tidying) and 9 (safety boundaries of continuous evolution) of "Understanding AI Agents in Depth". Versions and scope are recorded in `docs/architecture/reference-study.md`.

## Run language

The lesson runs in Chinese and in English. The teaching data text, the report labels and the answers built by code are in `locales/zh_CN.py` and `locales/en.py`; SQLite's own error text (for example the first problem of `integrity_check`) is SQLite's English original, and an English run contains no Chinese.

## Running and testing

```powershell
# This lesson's tests: real SQLite, a real writer thread, about ten-odd seconds
.\.venv\Scripts\python.exe -m unittest lessons.lesson_backup_upgrade.test_lesson -v
# Run on the web page (this lesson needs no model key)
.\.venv\Scripts\python.exe scripts/run_live.py backup-upgrade online-backup --url http://127.0.0.1:8765
# Validation
.\.venv\Scripts\python.exe scripts/validate_lessons.py
```

`run_live.py` produces no usage for exercises that call no model; until the lesson is `available` it is greyed out on the web page, and a `planned` lesson does not appear in the executable API.
