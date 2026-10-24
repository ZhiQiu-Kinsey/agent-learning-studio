---
doc_id: capabilities
title: Assistant Capabilities
version: 2026-10
supersedes: capabilities-2026-03
license: Original to this project; released under the repository license
---
## Implemented {#supported}

This assistant currently supports four things: answering from the material, generating practice questions, explaining a run trace, and saving and recalling learning progress.

Each of the four has a fixed acceptance case set.

## Not implemented {#not-supported}

Web search, multi-agent division of work and code execution are not implemented yet and exist only in the plan.

When asked about them, the assistant must say they are not implemented and must not pretend to do them.

## Scope {#scope}

The assistant answers only questions with grounds in this material, and for anything outside it the answer is that the material is insufficient.

## About this version {#changes}

This version takes effect in October 2026 and replaces the March 2026 version.

Main change: learning progress and trace explanation moved from planned to implemented.
