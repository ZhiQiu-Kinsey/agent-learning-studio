# Observability, usage and cost

**English** · [简体中文](README.zh-CN.md)

Lesson ID: `observability-cost`. Lesson numbers follow catalog order and appear only on the web page; files refer to lessons by title or ID.

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models.

## The problem this lesson solves

Earlier lessons only report the number of model calls and a `total_tokens` sum. When a user says "that took 6 seconds", the sum cannot tell which step took the time or which call was unnecessary, and when a provider does not report usage, a program can easily record 0 instead.

This lesson takes one fixed small task apart: check 4 travel expense receipts. For each one the model picks a category (transport, lodging, meals), then `lookup_rate` gets the exchange rate and `category_limit` gets the limit, the program works out the reimbursable amount and compares it with the human label. The runner keeps a ledger at the boundary of every call, one row per span, and then:

- ranks the slow steps by time;
- finds repeated executions by fingerprint;
- copies the usage the provider reported as is, and writes "not reported" when there is none;
- converts usage into an estimated cost only when a price source and date are given;
- after an optimization, compares on the same question set: first whether quality regressed, then what was saved.

## Files

| File | Contents |
| --- | --- |
| `runtime.py` | The runner: task data and the two tools, the `Tracer` ledger, `run_pass` (three strategies), `read_usage`, `repeated_groups`, `slowest`, `estimate_cost`, `regressions`, and the report assembly |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: the two system prompts, the 4 receipt descriptions, tool errors, report labels and values |
| `locales/__init__.py` | Field definitions of the message catalog |
| `fixtures.py` | Offline test fixture: answers with the human labels and reports scripted usage; it can switch usage off, drop it from the second response only, or make the batched request mislabel some receipts. Serves automated tests only |
| `test_lesson.py` | Behavior tests: reading usage, fingerprints, tools and structured errors, the three strategies, ledger rows tied to events, unreported never written as 0, cost estimates, regression detection, input validation, cancel and budget, no Chinese in English runs |
| `content.json`, `content.en.json` | Lesson content and its English overlay |
| `lesson.json`, `lesson.en.json` | Manifest (exercises, input presets, runner) and its English overlay |

## How to run

Offline tests (no model key; the tools really run, model replies and usage come from the fixture):

```bash
.venv/bin/python -m unittest lessons.lesson_observability_cost.test_lesson -v
```

Real runs: run it from the lab on the web page, or start the server and use the script (this uses model quota):

```bash
.venv/bin/python scripts/run_live.py observability-cost baseline --url http://127.0.0.1:8765
.venv/bin/python scripts/run_live.py observability-cost batched-compare --url http://127.0.0.1:8765 --locale en
```

The commands above were run once per exercise and language on 2026-10-21 (see the verification record).

## Exercises

| Exercise | Inputs | Model calls | Tool calls |
| --- | --- | --- | --- |
| Baseline: one request per receipt, no cache (`baseline`) | `strategy: baseline` | 4 | 8 |
| Tool cache only (`tool-cache`) | `strategy: tool_cache` | 4 | 5, plus 3 cache hits |
| Batched request, compared with the baseline (`batched-compare`) | `strategy: batched`, `compare_with_baseline: true` | 4 + 1 | 8 + 8 |

The counts assume the model gets all 4 categories right; a wrong category changes the `category_limit` arguments, so the report is what counts.

Other inputs:

- `rate_latency_ms`: how many milliseconds `lookup_rate` waits before each execution (0–1000, default 200). It stands in for a remote service, so a slow step is visible offline too.
- `price_input_per_m`, `price_output_per_m`, `price_currency`, `price_source`, `price_date`: the price table. `price_source` and `price_date` go together; without them no cost is converted. The estimate names the model, the source, the date and how many calls it covers, and says it is an estimate, not a bill.

## What to look at in the experiments

1. **Find repeated calls and slow steps** (baseline vs tool cache only)
   - the `usage` in the step 1 response, and how the first row of the `lesson.ledger` copies it;
   - the step 4 request body, identical to step 1 (r4 has r1's description);
   - "Repeated executions" and "Slowest step" in the bottleneck report;
   - with the cache, tool calls drop from 8 to 5 while the repeated model request remains.
2. **Batched request: what it saves, whether it gets worse** (batched request, compared with the baseline)
   - the batched request in step 5;
   - the guardrail "Quality did not drop" in the before-and-after report, and any item that went from passed to failed;
   - the change in reported tokens and in end-to-end time.

## Platform events and the lesson ledger

The platform records events for every run: `request`/`response` form a model span, `tool_call`/`tool_result` a tool span, events of one round belong to one step, and `response` carries `duration_ms`. These are the raw records. The lesson's `Tracer` keeps a derived ledger inside the runner: each row carries the step number (the event round) and a `call_id` (the id of the `tool_call` event), plus a fingerprint, the time the runner measured and the usage as reported. When the ledger and the events disagree, the events win.

## References

- Hugging Face Agents Course, Bonus Unit 2 (observability and evaluation)
- *Understanding AI Agents in Depth* (深入理解 AI Agent), chapter 7: agent observability, from benchmark reports to system improvements, and evaluation infrastructure for production agents; companion code `chapter7/agent-cost-analysis/tracer.py`
- Microsoft AI Agents for Beginners: `10-ai-agents-production` (AI agents in production: observability and evaluation)
- Claude Cookbooks: `observability/usage_cost_api.ipynb`, `cost_optimization/cost_optimization.ipynb`

Links and pinned versions are in the references at the end of the understand scene in `content.json`.
