---
doc_id: evaluation
title: Evaluation Notes
version: 2026-10
license: Original to this project; released under the repository license
---
## Splitting the cases {#sets}

The development set is for changing the version; the holdout set runs once after the version is chosen.

Holdout results must not be used to tune the prompt again, or the holdout set turns into a development set.

## Three verdicts {#verdicts}

Every case ends in one of three verdicts: passed, failed or unassessable.

A run that ended only says the run finished; it is not the same as passing acceptance.

## Pass-rate interval {#interval}

With very few cases, a pass rate is reported together with its Wilson interval.

When two versions are compared case by case, a sign test needs at least 6 cases with different results before it can be significant.

## Suite fingerprint {#fingerprint}

When the suite changes, both its version and its fingerprint must change.

Scores from suites with different fingerprints cannot be compared directly.
