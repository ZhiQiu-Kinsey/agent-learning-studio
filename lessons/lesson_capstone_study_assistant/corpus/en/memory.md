---
doc_id: memory
title: Persistent Memory Notes
version: 2026-10
license: Original to this project; released under the repository license
---
## Storage {#store}

Persistent memory lives in a SQLite file, one row per memory.

Each memory has three main fields, value, source and version, and source says where the memory came from.

## Recall {#recall}

Recall is read-only: read the memories first, then put them into the next request's user message as data.

The system prompt holds only rules, never memory content.

## Namespaces {#namespace}

A namespace keeps different learners' memories apart; with another namespace you cannot read someone else's records.

Namespaces and keys accept only ASCII identifiers of at most 32 characters that start with a letter.

## Version checks {#versions}

A write must carry the version the writer last read; a mismatch is a stale write and the old value stays.

Versions only go up; recreating a deleted key does not restart at 1.
