# Local delivery: start, configuration and credentials

**English** · [简体中文](README.zh-CN.md)

Lesson ID: `local-delivery`. Lesson numbers follow catalog order and appear only on the web page; files refer to lessons by title or ID.

Status: `planned`. The implementation, offline tests and the Chinese and English content are written; the offline tests really start child processes, but the lesson has not been through an acceptance run on the web page yet, so it stays greyed out there.

## The problem this lesson solves

The earlier lessons all ran on your own machine: dependencies installed, environment variables already set. Hand the tool to someone else and the missing pieces show up one by one: the terminal stays quiet for three seconds, is the process running, where is it stuck, what does the log say? Worse, the log someone pastes has an API key in it.

This lesson does not call a model and needs no key. It really starts `notes_app`, a small local service in the lesson directory, and runs delivery checks that read the exit code, port, log and files of a real child process:

- configuration has three layers (default < settings file < environment) and every value carries its source; missing required settings, a credential in the settings file or a mistyped key are refused before listening, naming every problem at once, with no value in the error;
- the liveness probe `/health` and the readiness probe `/ready` answer separately; a hang, a missing readiness and a busy port are each reported honestly at the limit;
- stopping sends `SIGTERM` first and then kills the whole process group; killing only the main process leaves the background worker behind (an orphan process);
- the log is one JSON object per line; a credential is reported only as "set" plus its source; when a faulty version writes its whole configuration into the log, the scan locates the line number and the setting, and what is shown is redacted;
- after the whole group is killed the data is intact, restored on restart, and a repeated write is not duplicated; an incompatible new configuration is refused before listening, and with the backup put back the service recovers.

## Files

| File | Contents |
| --- | --- |
| `notes_app.py` | The service under check: standard-library `http.server`, `/health`, `/ready`, `/config`, `/notes`, JSON logs, a background worker process, a clean stop on SIGTERM; `--fault` injects a defect (hang without listening, warm-up that never ends, configuration written into the log) and serves the checks only |
| `settings.py` | Three-layer configuration: default < settings file < environment, collects every problem, reads a credential from the environment only; shared by the app and the checks |
| `notes_store.py` | The data file: write a temporary file and rename it, and `op_id` makes a repeated write take effect once |
| `launcher.py` | The runner side: an allow-listed environment, spawning the child, waiting for the port file, probing, SIGTERM first and the process group after, whether a process is really gone |
| `logscan.py` | Reading the log back: is it structured, are the lifecycle events all there, is a credential value in it, redaction |
| `runtime.py` | The runner: four scenarios, one `lesson.report` per step, plus the `lesson.process`, `lesson.probe` and `lesson.start_failed` events |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: report titles, check labels and details, metric labels, answers |
| `locales/__init__.py` | Field definitions of the message catalog |
| `test_lesson.py` | Behavior tests: configuration rules, the data file, the log scan, real child processes started and stopped, the four scenarios (both run languages), the credential in no event, no process left after a cancel, input validation |
| `content.json`, `content.en.json` | Lesson content and its English overlay |
| `lesson.json`, `lesson.en.json` | Manifest (exercises, runner) and its English overlay |

There is no `fixtures.py`: the lesson calls no model, so it needs no deterministic model replies; the checks use real processes.

## How to run

Offline tests (no key, no network; they really start child processes and take about 20 seconds):

```bash
.venv/bin/python -m unittest lessons.lesson_local_delivery.test_lesson -v
```

Once the lesson is open, pick an exercise in the lab on the web page; no model has to be configured first. Each exercise starts and stops a few child processes in a temporary directory and removes both the directory and the processes when it ends.

The "key" in this lesson's exercises is a fake key made up for each run (`sk-demo-` plus random characters). The lesson never reads your real key, and the fake one appears in no event, no log excerpt and no answer.

## Exercises

| Exercise | Scenario | Real child processes | About |
| --- | --- | --- | --- |
| Configuration layers: missing settings, sources and the credential (`config-layers`) | Predict the three layers and have a real child report them; configure nothing; a credential and a mistyped key in the settings file | 3, two of which exit before listening | 1 s |
| Starting, readiness and stopping (`startup-probe`) | A normal start and stop; a hang; alive but not ready; a busy port; killing only the main process versus the whole process group | 5 | 5 s |
| Structured logs and credential leaks (`logs-and-secrets`) | The log of a normal run; a faulty version that writes the configuration into the log | 2 | 1.5 s |
| Crash restart, repeated write and configuration rollback (`restart-rollback`) | Write, back up, kill the whole group; restart, resend; a new configuration that cannot be read; put the backup back | 4 | 2 s |

Inputs you can change (the lab's parameter panel):

- `scenario`: which scenario runs; each of the four exercises fixes it;
- `startup_timeout_ms` (default 1200): how long to wait for the app to listen; set too small, even a normal start times out;
- `ready_timeout_ms` (default 1200): how long to wait for `/ready` to return 200 after listening; shorter than the warm-up, a normal start is honestly reported as not ready;
- `warmup_ms` (default 400): the dependency warm-up time the app simulates.

## What to look at in the experiments

1. **Configuration, credentials and logs** (`config-layers` and `logs-and-secrets`)
   - how many settings each of the three layers supplied, and the `model` row showing what the file and the environment each say and which one wins;
   - `lesson.start_failed` in rounds 2 and 3: `problems` holds only setting names and problem codes, and the exit code is 2;
   - in the log group: the lifecycle events are all there; in the faulty run "the log holds no credential value" fails, the line shown contains `[REDACTED:api_key]`, and the delivery gate blocks.
2. **Starting, readiness and stopping** (`startup-probe`)
   - the probe timeline: `/health` is 200 at once, `/ready` is 503 during warm-up and 200 afterwards;
   - `alive` in the round 2 `lesson.start_failed`: at the timeout the process was still alive, so it was stuck;
   - `limit_ms` of `not_ready` in round 3; the exit code 3 and `EADDRINUSE` in round 4;
   - `orphans` of `leader_killed` in round 5: 1 process left after killing only the main process, 0 after reaping the process group.
3. **Crash restart and configuration rollback** (`restart-rollback`)
   - after the whole group is killed and restarted, 2 notes are read; resending `op-2` is not duplicated and the new `op-3` is written;
   - the new configuration that cannot be read: `settings_version` not supported, `model_id` an unknown key, `model` missing;
   - after the rollback, the digests of both files equal the ones from before.

## What this lesson does not cover

- Only one small service on this machine. No cloud deployment, no multiple users, no container orchestration.
- No model or MCP probe. Whether a real model is usable has to be verified with a real request in the model connection settings; "configured" is not "verified", and a provider that has not been verified must not be marked as usable.
- A fake key proves the logic of the check, not that your real key management is right. The log scan finds only known values that appear as they are.
- The rollback covers only the settings file; rolling back a data-format migration is not shown.
- What is killed is a process group, not a power cut; whether the disk cache survives a power cut depends on the file system and the hardware.

## References

- Microsoft AI Agents for Beginners: `16-deploying-scalable-agents` (from prototype to production, smoke tests), `17-creating-local-ai-agents` (privacy, cost and limits of running locally), `10-ai-agents-production` (observability and evaluation)
- *Understanding AI Agents in Depth* (深入理解 AI Agent): the companion `chapter4/DOCKER_DEPLOYMENT.md` (environment variables, health checks, production notes) and chapter 7, "evaluation infrastructure for production agents"
- Learn Claude Code: `s15_integrated_harness` (process-group cleanup, permissions and background tasks)

Links and pinned versions are in the references block at the end of the understanding scene of `content.json`.
