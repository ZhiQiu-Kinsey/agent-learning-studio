# Security Policy

## Supported versions

Agent Learning Studio has no versioned releases yet. Security fixes land on the `main` branch only; please reproduce issues against the latest `main`.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Other branches and older commits | No |

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's private vulnerability reporting: open this repository's **Security** tab and choose **Report a vulnerability** ([direct link](https://github.com/ZhiQiu-Kinsey/agent-learning-studio/security/advisories/new)). Don't open a public issue, pull request or discussion for a security problem.

Include what you can:

- the affected component (backend route, runner, provider adapter, frontend, script);
- steps to reproduce, and the commit you tested;
- the impact you expect.

**Never include real API keys or other credentials in a report.** Use placeholder values; if a key was exposed, revoke it with your provider first.

We'll acknowledge the report, keep you informed while we investigate, and credit you in the fix unless you prefer otherwise. This is a small volunteer-run project, so please allow reasonable time for a response.

## Scope and design assumptions

Agent Learning Studio is a single-user learning tool meant to run on your own machine. Please keep these assumptions in mind when assessing an issue:

- **Local only.** The server binds to `127.0.0.1` and has no user accounts or authentication. Exposing it on a network or sharing it between users is not a supported deployment; that would need its own design for identity, storage and execution isolation. Bugs that let a remote web page or another host reach or abuse the local server are in scope.
- **Lesson code is not a sandbox.** Lesson tools are ordinary Python running in the server process with your user's permissions. Lessons that execute model-generated code must have an isolation design before they ship. A way for model output or lesson input to escape the documented tool boundaries is in scope.
- **API keys stay in the backend.** Keys come from environment variables or `local_config.py` (git-ignored; template in `local_config.example.py`). Keys entered in the browser are kept only in backend memory and are never echoed back. Run events are redacted before they are stored in `.runtime/runs.sqlite3`. Any path that leaks a key into run records, logs, API responses, the browser or browser storage is in scope.
- **Source access is restricted.** The source API only serves files listed in lesson manifests. Reading arbitrary paths through it is in scope.

Out of scope:

- issues that require an attacker to already control your machine, your user account or your `local_config.py`;
- usage costs from runs you start yourself against a real model;
- vulnerabilities in third-party dependencies (for example LiteLLM, FastAPI or frontend packages) that don't affect this project — please report those upstream. Dependency updates are tracked by Dependabot.
