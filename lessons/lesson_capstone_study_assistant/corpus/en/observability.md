---
doc_id: observability
title: Observability Notes
version: 2026-10
license: Original to this project; released under the repository license
---
## The ledger {#ledger}

The ledger keeps one row per span: a model request, a tool call and a cache hit each take a row.

Each row carries a step number, a duration and a fingerprint, which lead back to the raw events the platform recorded.

## Usage {#usage}

Usage that the provider did not report is written as not reported, never estimated and never written as 0.

A tool call has no token usage and is written as not applicable, which is different from not reported.

## Repeated calls {#repeats}

The second and later executions with the same fingerprint count as repeated calls, and a cache hit does not.

A repeated model request spends extra tokens and time for nothing.

## Cost {#cost}

Cost is only an estimate: usage times a price table, and the price must name its source and date.

Without a price source only usage is reported, never an amount of money.
