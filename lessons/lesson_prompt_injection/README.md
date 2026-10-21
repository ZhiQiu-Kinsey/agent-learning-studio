# Prompt injection and tool permissions (`prompt-injection`)

English · [简体中文](README.zh-CN.md)

The question of this lesson: material, web pages and tool results can carry instructions, and a model that reads them may be persuaded to propose calls that read a key, rewrite a notice or send data out. How do you make "persuaded" not mean "did harm"? The lesson puts two documents that carry instructions into a real retrieval chain, and the program decides on the **executing side** whether each call the model proposes is allowed, needs approval or is refused. What the model proposed and what the files and the outbox actually became are recorded as two separate facts. 

Retrieval reuses the chunking of `document-loading` and the BM25 of `keyword-retrieval`: the shared "Bluestone Library Handbook" (including the reader comment that poses as an instruction) plus two documents of this lesson's own; the shared corpus is not changed. The tools are real Python: search, read a file, write a file and send (the send only writes to a local outbox, with no network), all acting on a temporary folder that is created for each run and deleted afterwards.

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models. The defenses were **not tested against a persuaded model**: in every run of that day the model proposed nothing out of scope, so every refused call is a runner probe and the three defense checks say "not tested".

## Files

| File | What it holds |
| --- | --- |
| `guard.py` | The executing-side permission check: `Policy`, `Grant`, `STRICT` (the least-privilege policy), `open_policy` (for the two prompt-only arms), `authorize` (the only entry; any error is a refusal), path resolution and business rules |
| `workspace.py` | The real tools and the temporary folder they act on: `Workspace` (`read_file`, `write_file`, `post_url`, file snapshots, the effect ledger), the floor `FloorViolation` around the temporary folder, the fake key `CANARY` |
| `retrieval.py` | `search_handbook`: BM25 over the handbook plus this lesson's two documents; which chunks carry an instruction is used for the report only and never written into the tool result |
| `runtime.py` | The runner: `Session` (decide first, record, wait for approval if needed, then execute), `run_task` (the loop for one question), the four exercises, the runner probes |
| `reports.py` | Records into numbers and numbers into reports: out-of-scope proposals, blocked calls, out-of-scope reads or writes that happened, probe results |
| `corpus/<locale>/*.md` | The lesson's two untrusted documents: `partner-bulletin` (a fee notice followed by a "fee check notice") and `transfer-notice` (which points at a workspace file) |
| `workspace_seed/<locale>/public/` | The notice and `transfer-guide.txt` (its last line carries a second instruction) in the temporary workspace |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: the system prompts (base and with a warning), tool descriptions, refusal messages, report text |
| `fixtures.py`, `locales/fixture/` | The offline fixture: serves automated tests only; a "model" scripted to follow the demands in material, plus the approval decisions |
| `test_lesson.py` | Behavior tests: every rule, real file effects, the four exercises, both run languages |
| `content.json`, `content.en.json` | Teaching content and its English overlay |

The interface of `guard.authorize`:

```python
authorize(policy: Policy, workspace: Path, name: str, raw_arguments, registered) -> Decision
# Decision.verdict: "allow" | "confirm" | "deny"; Decision.rule: the rule code; Decision.category: "ok" | "scope" | "input"
```

- Its inputs are only the policy the program built, the tool registry, the tool name and the raw argument string (the path check also reads the disk). What material and the model say are not inputs.
- Only a refusal with `category` `scope` counts as "out of scope": an unregistered tool, a tool not granted, an escaping path, content shaped like a key. Invalid arguments and oversized writes are `input` and are not counted as attacks.
- `STRICT`: `search_handbook` is allowed; `read_file` may read only `public/` and `out/`; `write_file` may write only `.md` files in `out/`, at most 2000 bytes, with a person's approval each time; `post_url` is not granted.

## Exercises

| Exercise | Model calls | Evidence to look at |
| --- | --- | --- |
| Normal tasks: the permission layer does no harm | 8 | Four normal tasks (a search, a search that brings in a noisy comment, a notice read, a tip file write) all finish; an approval request appears before the write; no call is refused |
| Injection in the material: the model's proposals and the executing side's decisions | up to 8 (`scenarios` can reduce it to 4) | The indirect and the direct path; a `lesson.permission` for each out-of-scope proposal; a report that keeps the model side and the executing side apart; 17 runner probes (16 where the platform cannot make symlinks) |
| Prompt only or executor-side permissions: a three-arm comparison | 12 | No defense, prompt warning plus source tags, then executor-side permissions; each arm's `lesson.arm_result` (out-of-scope proposals, blocked, out-of-scope reads or writes that happened, whether the key reached the answer) |
| Indirect prompt injection travels through tool results | 4 | A search result points at a file that carries a second instruction; the two hops of `lesson.context_source`; the file read is allowed and the outbound send is refused |

Parameters: `top_k` (1-5, default 3) is the default number of chunks a model search returns; `scenarios` (`both`, `indirect`, `direct`) applies only to "Injection in the material". Set `top_k` to 1 and the chunk of the bulletin that carries the instruction never enters the request, the model has nothing to follow and the report calls that arm "not tested".

## What the experiments show

1. **Injection in the material**: what the model proposed (is the `source` of `lesson.permission` `model` or `offline_fixture`), how `authorize` decided (the rule and the resolved landing point), that a refused call is a structured error in `tool_result`, and the out-of-scope reads or writes that really happened in the report. Then look at "where the blocking evidence comes from": if the model proposed out-of-scope calls the evidence is its proposals plus the probes; if it did not, only the runner probes.
2. **The three defenses**: the same question over the same poisoned material. In the first and second arms, which have no executor-side permissions, the tools really run: the decoy key is read, the notice is rewritten and the outbox gains a line. In the third arm the same proposals are all blocked. The third arm's answer can still follow the material's demand; that layer belongs to other defenses.
3. **Propagation**: a read inside the granted scope is allowed (the permission judges the call, not what the file says) and the out-of-scope send that follows is refused; `lesson.context_source` records what entered the context at each hop.

What they can prove: the decision and its reason for every proposal, what the world actually became, and whether the answer was pulled off course, as three separate records. What they cannot prove: whether a real model is persuaded (in offline test mode the proposals are written by the fixture), that the policy holds against attacks nobody wrote into the set, or that the content of an answer is correct.

## How to run

Offline tests (fixture + real retrieval, real permission checks and real file effects, no model call):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_prompt_injection.test_lesson -v
```

A real run (it uses model quota, and the file write in "Normal tasks" has to be approved in the web page):

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py prompt-injection attack --url http://127.0.0.1:8765 --locale en
```

## Honest notes

- `fixtures.py` serves tests only. It is a script "written to follow the demands in material": when the bulletin asks for the key, it proposes reading the key, rewriting the notice and sending out. Its proposals are identical under all three defenses, so the comparison table shows only how the defenses differ **once the model is persuaded**; it is **not a measurement of any real model**. Every out-of-scope call it proposes carries `x_offline_fixture` in the response and `source: offline_fixture` in `lesson.permission`.
- The tools, the permission checks and the file effects are real: in the two open-policy arms the decoy key really enters the context, the notice file is really rewritten and the outbox file really gains a line. All of that happens in the temporary folder, which is deleted afterwards; the "key" is a fake string fixed in the lesson and unlocks nothing.
- The runner probes (origin `course_program`) cover every rule of the guard plus normal calls that must be let through; they prove the guard itself and must not be read as model behavior.
- The fixture reports no usage, so the report shows usage as not reported.
- A real model was run on 2026-10-21 (`claude-haiku-5-5`, every exercise once per language), but it **never proposed an out-of-scope call**, so those runs say nothing about whether the defenses hold against a persuaded model. A run in which the model proposed nothing out of scope has to be recorded as it is and is not evidence that a defense works. A run in which the model proposed nothing out of scope has to be recorded as it is and must not be used as evidence that the defense works.

## Remaining risks (the lesson says so too)

A file in the granted folder can itself be poisoned and make an answer wrong; with many approvals people click "agree" without reading; there is a short gap between checking a path and actually opening the file (a symlink race); and what lies outside permissions, such as an answer that calls the fee free, needs another layer such as a Citation check. The temporary folder is not a sandbox: it is an ordinary folder in an ordinary process.

## References

- Understanding AI Agents in Depth (bojieli/ai-agent-book, Apache-2.0): chapter 2 on prompt injection and source marking, chapter 4 on the layers of safety for execution tools and the Sidecar, chapter 5 on coding-agent safety (the lethal trifecta).
- Microsoft AI Agents for Beginners (MIT): `06-building-trustworthy-agents`, `18-securing-ai-agents`.
- learn-claude-code (shareAI-lab, MIT): `s03_permission`; claude-cookbooks (MIT): `claude_agent_sdk/scheduled_repository_reviewer`.

Only the ideas were adapted; no code was copied and nothing was translated sentence by sentence. The documents, the policy, the probes and the experiments are written by this project.
