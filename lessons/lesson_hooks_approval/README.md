# Hooks and the approval gate (`hooks-approval`)

English · [简体中文](README.zh-CN.md)

This lesson asks one question: when an Agent's writing tools are about to change something for real, how do you add checks without touching every tool, let a person nod at the critical moment, and guarantee that what runs after the nod is the very set of arguments the person saw? The answer has four layers. Hooks before the tool rule on every call (allow, deny, rewrite the arguments, ask for approval). A call that needs approval puts the run into `paused` and waits for a person to approve, reject or let it time out. After approval the tool runs with the arguments from the decision, and just before it runs the argument digest is checked once more. Hooks after the tool mask sensitive fields, read the write back and hash what is returned to the model.

The lesson needs a live model connection (the model proposes the calls), but an approval accepts only the decision of a person on the page; the offline test mode uses a scripted "model" and a scripted "approver", and the web page has no simulation entry. The prerequisite is `async-concurrency`; the text continues from `tool-proposals` (the model only proposes calls) with the gate between proposal and execution. The next lesson is `human-in-the-loop` (recovering from a checkpoint after a process restart), `bash-coding-agent` uses approval on every command, and `reliable-tools` covers what happens when one write runs twice.

> **The desk is a temporary directory, not an isolated environment.** The four tools really read and write files, but only inside a temporary directory made for this run, never over the network, and the directory is deleted when the run ends. The tools are ordinary Python functions in the local process: hooks and approval decide which calls may run, not what a running call can do.

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models.

## The desk and the four tools

`Desk` in `store.py` seeds four tickets in a fresh temporary directory for every run (`TKT-101` to `TKT-104`, with made-up customer phone numbers and emails) and an empty outbox file `outbox.jsonl`.

| Tool | Read or write | What it does | Risk the hooks assign |
| --- | --- | --- | --- |
| `list_records` | read | Lists the id, title, status and owner of the tickets | allow, no approval |
| `read_record` | read | Reads one ticket; the customer's phone and email are masked by a hook after the tool | allow, no approval |
| `update_record` | write | Changes `status`, `owner` or `note` of one ticket | `medium`; closing a ticket (`status` set to `closed`) and changing the owner are `high` |
| `send_notice` | write | Appends a notice to the outbox, which cannot be taken back | `high`; `critical` when the recipient is the broadcast address `all@corp.example` |

A tool function only does its job and carries no policy; all policy is in the hooks. Every tool has a Pydantic argument model (`ARGUMENT_MODELS` in `gate.py`), and one argument too many or too few is `invalid_arguments`, refused before any rule runs.

## The hooks

The hooks before the tool run in order, and the order is part of the design (rewrite first, then deny, then ask):

| Hook | Verdict | Rule |
| --- | --- | --- |
| `normalize_arguments` | `rewrite` | Upper-case the ticket id, lower-case the recipient and the status value, trim whitespace; arguments that are already normal return `allow`, so the rewrite is stable |
| `record_scope` | `deny` | Deny a ticket id that is not `TKT-` plus three digits; path-traversal spellings are stopped here |
| `recipient_domain` | `deny` | Deny a recipient that is not a mailbox under `corp.example` |
| `field_allowlist` | `deny` | Deny a field outside `status`, `owner`, `note`, or an invalid status value |
| `risk_level` | `allow` or `ask` | Read tools pass; a write tool needs approval and gets a risk level; an unclassified tool is denied (`tool_not_classified`) |

The rules of the chain (`run_pre_hooks` in `hooks.py`): `deny` stops at once; `rewrite` hands the new arguments to the hooks after it; `ask` is noted and the highest risk of several wins. The hooks after the tool are `redact_customer_data` (mask the customer's contact details), `verify_effect` (read the write back from the file) and `audit_trail` (hash what is returned to the model; it runs after the masking).

## Exercises

| Exercise | Task | What to look at |
| --- | --- | --- |
| Read-only passes, writes need approval (`approve-write`) | Look at and change `TKT-102`, then notify its owner | No approval card for the reads; one card for each of the two writes; `no-early-effect` and `args-match-approval` pass |
| Rejection and timeout (`reject-timeout`) | Change `TKT-103` and notify the people concerned | The broadcast notice is rejected and the note goes to the model; the second notice times out; `refused-not-executed` |
| Edited arguments pass the rules again (`edit-recheck`) | Notify the owner of `TKT-104`, with an editable card | The recipient is edited to outside the company domain, and `lesson.hook_recheck` still stops it after approval |
| Arguments swapped after approval (`swap-guard`) | Notify `alice@corp.example`, and after approval a demo fault swaps the recipient | `match` in `lesson.guard` is false, `approval_mismatch`, an empty outbox |

There are four inputs: `task` (the four task texts above), `approval_timeout_s` (the approval wait limit, 3 to 300 seconds, preset to 20 for `reject-timeout` and 60 for the others), `allow_edit` (whether the card allows editing, on only in the `edit-recheck` preset) and `late_rewrite` (deliberately rewrite the recipient after approval, on only in the `swap-guard` preset). `late_rewrite` is a teaching fault the runner makes from an input, marked `origin: fault_injection` in the event; it is not a simulation of a real attack.

## The events of one write

```text
tool_call                  the call the model proposed (as written, not yet executed)
lesson.hook_pre            chain before the tool: steps, changes (when rewritten), risk or denied_by, desk digest
approval_requested         approval request: kind, summary, payload, payload_digest, risk, timeout_s, editable
approval_resolved          decision: outcome, decided_by, note, edited (with payload when edited), waited_ms
lesson.hook_recheck        only when the arguments were edited at approval: re-check result, edited_fields, denied_by
lesson.guard               approved_digest, attempted_digest, match, and injected for the fault
lesson.hook_post           hooks after the tool: redacted, verified, result_digest
tool_result                the gate's result: ok, executed, error_type and so on, which the model reads next round
```

A read-only call has only `tool_call`, `lesson.hook_pre`, `lesson.hook_post` and `tool_result`. A call refused by a hook has none of the later ones; a rejected or timed-out call has the `approval_*` pair but no `lesson.guard` and no `lesson.hook_post`.

The result the model reads is `{"ok": true, "result": {…}}`: the outer `ok` says the platform handled the call, and the inner `ok` and `executed` are the tool's result. The inner `error_type` can be `invalid_arguments`, `hook_denied`, `approval_rejected`, `approval_timeout`, `approval_mismatch`, `edit_invalid` or `edit_not_normalized`, or the tool's own `record_not_found` or `unknown_owner`: an approval does not promise success.

## The three reports

- The first `lesson.report` (hooks and approval settings): the phase, role and rule of each hook, the approval wait limit, whether cards are editable and whether the rewrite after approval is on.
- The second `lesson.report` (call ledger): for each call the risk, hook verdict, approval and outcome, and three digests: approved, executed and sent back to the model. Five checks: `no-early-effect` (the digest of the whole desk is the same before and after each approval wait), `args-match-approval` (the digest of what ran equals the approved one), `refused-not-executed` (calls that were rejected, stopped or timed out left the files unchanged), `summary-covers-args` (the summary states the key arguments) and `customer-data-redacted` (no raw customer contact details in what went back to the model). When there is nothing to check, a check gives no verdict instead of claiming a pass.
- The third `lesson.report` (what really changed on the desk): the ticket changes and the outbox read from the files after the run, set against the ledger (`effects-match-ledger`), with the model's last sentence last.

The final answer is written by the runner: the number of calls, the calls that did not run and why, and the actual changes first, then the model's own words with a note that the records above decide.

## Running

Offline tests (the model and the approval decisions are scripts in `fixtures.py`; the tools really run in a temporary directory; the decisions come from `testing.approval_factory` in `lesson.json` and are recorded as `decided_by: offline_fixture`):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_hooks_approval.test_lesson -v
```

Once it is available, a live run needs a configured model; start the service on another port and leave the 8765 you are using alone:

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8790
.\.venv\Scripts\python.exe scripts/run_live.py hooks-approval approve-write --url http://127.0.0.1:8790 --ask-approvals
```

On the web page you approve or reject the card and may write a note; the card of `edit-recheck` also lets you edit the arguments. The page has no automatic approval, and `run_live.py --ask-approvals` shows the same card in the terminal. Replays, recordings and "the last run" are read-only and cannot approve any more.

## What it proves and what it does not

- It proves: for this run, which hook rewrote or stopped each call, the risk of each call that needed approval, who decided, whether the tool ran before approval (by comparing the desk's digest before and after), whether the digest of what ran equals the approved one, and which changes really happened in the files.
- It does not prove: that the tools are safe. The desk is plain files in a temporary directory with no isolation; a hook enforces only the rules written into it; an approval shows that someone saw the card, not that the arguments are right, and it cannot stop a person misreading.
- The "model" and the "approver" in the offline tests are scripts and stand for no real model or person; the swap in `swap-guard` is a fault made on purpose. Which calls a real model proposes, and whether it changes approach after a rejection note, is for your own run records to say.
- Live runs: all four exercises were run once per language on 2026-10-21. After the task wording was aligned with the seeded tickets, every run showed its approval cards. In the repeat the model still wrote the ticket number in capitals itself, so `normalize_arguments` rewrote nothing (`rewrite-on-read` does not hit). See the verification record.

## Files

| File | What it is |
| --- | --- |
| `hooks.py` | `HookResult` and the four verdicts, the chain before the tool `run_pre_hooks`, the hooks after the tool |
| `gate.py` | `Gate`: shape check, hooks, approval (`request_approval`), the re-check after an edit, the digest check, execution, structured refusals |
| `store.py` | `Desk`: ticket files and an outbox in a temporary directory, and the content digest that can show "nothing changed" |
| `runtime.py` | The inputs, the four tool definitions, the Agent loop, the three reports and the final answer |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: system prompt, tool descriptions, the four tasks, refusal messages, report labels and the final answer |
| `fixtures.py` | The scripted "model" and approval decisions for offline tests, serving automated tests only |
| `test_lesson.py` | Behavior tests: the chain and its order, each approval outcome, the re-check after an edit, the digest check, masking, evidence from the files, stopping and both run languages |
| `content.json`, `content.en.json` | The teaching content and its English overlay |

## References

The lesson draws on the three permission gates and the hook events of [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) (MIT), on the execution-layer guardrails, pre-approval and risk ratings of chapters 1, 4 and 5 of "Understanding AI Agents" (Apache-2.0), on the human-in-the-loop notebook in `06-building-trustworthy-agents` of [AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) (MIT; gate before the action, risk tiers, audit records), and on the "control versus freedom" section of the [Hugging Face Agents Course](https://github.com/huggingface/agents-course) (Apache-2.0) about flows that need a human in the loop. The code, prompts and experiments are written for this project and no upstream code was copied. Pinned versions, reading scope and licenses are in `docs/architecture/reference-study.md`, and the platform interface for approvals is in section 7 of `docs/architecture/event-envelope-v2.md`.
