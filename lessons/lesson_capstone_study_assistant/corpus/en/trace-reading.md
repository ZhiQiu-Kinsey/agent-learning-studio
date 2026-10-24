---
doc_id: trace-reading
title: Trace-Reading Notes
version: 2026-10
license: Original to this project; released under the repository license
---
## Event types {#events}

A run is a sequence of events: request, response, tool_call, tool_result, and finally answer and done.

A request event records the request body that was actually sent, and a response event records what the provider returned.

## Spans {#spans}

One model request or one tool call is a span with a start and an end time.

Events of the same round are grouped under one step.

## Reading the ledger {#reading}

To read a ledger, first find the row with the longest duration, then see whether it is a model request or a tool call.

The number of chunks a search returned is in the tool result's hits, and usage is in the response's usage.

## Replay {#replay}

Replay only reads events that were already recorded; it neither asks the model again nor runs the tools again.
