---
doc_id: tool-calling
title: Tool-Calling Notes
version: 2026-10
license: Original to this project; released under the repository license
---
## Call proposals {#proposal}

The model only proposes a call; the program is what actually runs the tool.

A proposal carries a function name and its arguments as a JSON string, which the program parses before running.

## Pairing results {#pairing}

Every tool result carries the call id, and the next request uses it to pair the result with its proposal.

When a call id does not match, the request is malformed and most providers reject it.

## Tool failures {#failure}

A failing tool returns a structured error: ok is false, with the fields error_type and error.

A failure does not crash the program; the model reads the error on the next round and can fix its arguments.

## Round limit {#round-limit}

The tool loop has a round limit, and the basic lessons allow at most 3 rounds.

If the rounds run out without a final answer, the program reports an error instead of returning a half result.
