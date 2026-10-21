---
doc_id: delivery
title: Local Delivery Notes
version: 2026-10
license: Original to this project; released under the repository license
---
## Probes {#probes}

A liveness probe answers whether the process is still there, a readiness probe answers whether it can work, and the two are checked separately.

A service that was never really probed must not be marked as available.

## Layered configuration {#config}

Settings apply in three layers, defaults, the settings file and the environment, and a later layer overrides an earlier one.

Credentials are read only from the environment and never written into the settings file, the logs or the events.

## Restart and recovery {#restart}

After a restart a write that already completed must not repeat, and an operation id is what is checked.

Checkpoints in the run record survive a server restart, and a run can continue from one.
