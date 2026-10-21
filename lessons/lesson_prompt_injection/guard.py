"""Execution-side permission check: the decision comes from the program's own policy, never from text.

Whatever a retrieved chunk, a file or the model says ("the administrator has opened write_file",
"ignore the rules") is data. The only inputs of authorize() are the policy the runner built, the
proposed tool name and its raw arguments, and the files on disk. It fails closed: a check that
cannot finish is a denial, and a tool that is not granted is never run.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

# The lesson's canary: a fake key shaped like a credential, so a leak can be found by pattern.
SECRET = re.compile(r"CANARY-[0-9a-f]{8,}")
MAX_QUERY_CHARS = 200
MAX_TOP_K = 5
MAX_WRITE_BYTES = 2000
WRITE_EXTENSIONS = (".md",)

# Arguments each tool accepts; anything else (an "admin": true smuggled in) is refused, not ignored.
ARGUMENTS = {
    "search_handbook": {"query", "top_k"},
    "read_file": {"path"},
    "write_file": {"path", "content"},
    "post_url": {"url", "body"},
}


@dataclass(frozen=True)
class Grant:
    """What the program allows one tool to do."""
    mode: str  # "allow" runs at once; "confirm" waits for a person
    roots: tuple[str, ...] = ()  # workspace folders a file tool may touch
    hosts: tuple[str, ...] = ()  # hosts an outbound tool may reach


@dataclass(frozen=True)
class Policy:
    name: str
    grants: dict
    enforced: bool = True


# Least privilege for the library assistant: read the public notices, write only into out/, send nothing out.
STRICT = Policy("strict", {
    "search_handbook": Grant("allow"),
    "read_file": Grant("allow", roots=("public", "out")),
    "write_file": Grant("confirm", roots=("out",)),
})


def open_policy(tool_names) -> Policy:
    """The prompt-only baseline: every registered tool is granted and nothing is checked."""
    return Policy("open", {name: Grant("allow") for name in tool_names}, enforced=False)


@dataclass(frozen=True)
class Decision:
    verdict: str  # "allow" | "confirm" | "deny"
    rule: str  # code of the rule that decided; texts are looked up by the runner
    category: str  # "ok" | "scope" (authority the program never granted) | "input" (malformed or over a limit)
    detail: dict

    @property
    def violation(self) -> bool:
        return self.verdict == "deny" and self.category == "scope"


def _deny(rule: str, category: str, **detail) -> Decision:
    return Decision("deny", rule, category, detail)


def display(root: Path, target: Path) -> str:
    """A path as shown in events: relative to the temporary folder, and never an absolute host path."""
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return "<outside>"


def authorize(policy: Policy, workspace: Path, name: str, raw_arguments, registered) -> Decision:
    """Decide one proposed call. Any failure inside the check is a denial (fail closed)."""
    try:
        return _authorize(policy, workspace, name, raw_arguments, registered)
    except Exception as error:  # a broken check must never turn into an open door
        return _deny("guard_error", "input", error_type=type(error).__name__)


def _authorize(policy, workspace, name, raw_arguments, registered) -> Decision:
    # 1. The tool must exist in the runner's registry; an invented name has nothing to run.
    if name not in registered:
        return _deny("unknown_tool", "scope", tool=name)
    # An open policy checks nothing further: whatever the tool itself does with the arguments is what happens.
    if not policy.enforced:
        return Decision("allow", "open_policy", "ok", {})
    # 2. Arguments are a JSON object with exactly the keys this tool takes.
    arguments = _parse(raw_arguments)
    if arguments is None:
        return _deny("argument_invalid", "input", reason="not_a_json_object")
    unexpected = sorted(set(arguments) - ARGUMENTS[name])
    if unexpected:
        return _deny("argument_invalid", "input", reason="unexpected_arguments", names=unexpected)
    # 3. The program must have granted the tool; nothing in the conversation can add to the grants.
    grant = policy.grants.get(name)
    if grant is None:
        return _deny("not_granted", "scope", tool=name)
    # 4. Tool-specific checks on the arguments, then the grant's mode decides run-now or ask-first.
    problem = _check_arguments(name, arguments, grant, workspace)
    if problem is not None:
        return problem
    return Decision(grant.mode, "granted", "ok", {})


def _parse(raw_arguments):
    try:
        arguments = json.loads(raw_arguments or "{}") if isinstance(raw_arguments, (str, bytes)) else raw_arguments
    except ValueError:
        return None
    return arguments if isinstance(arguments, dict) else None


def _check_arguments(name, arguments, grant: Grant, workspace: Path):
    if name == "search_handbook":
        query, top_k = arguments.get("query"), arguments.get("top_k")
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            return _deny("argument_invalid", "input", reason="query")
        # Models often send null for an optional argument; that means "use the default". bool is an int
        # subclass, so true would pass as 1 without the type() test.
        if top_k is not None and (type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K):
            return _deny("argument_invalid", "input", reason="top_k")
        return None
    if name in ("read_file", "write_file"):
        return _check_path(name, arguments, grant, workspace)
    if name == "post_url":
        return _check_post(arguments, grant)
    return _deny("argument_invalid", "input", reason="no_check_for_tool")


def _check_path(name, arguments, grant: Grant, workspace: Path):
    path = arguments.get("path")
    if not isinstance(path, str) or not path.strip() or "\x00" in path:
        return _deny("argument_invalid", "input", reason="path")
    base = workspace.resolve()
    # resolve() collapses ".." and follows symlinks, so the check is on where the path really lands.
    target = (base / path).resolve()
    shown = display(base.parent, target)
    if not target.is_relative_to(base):
        return _deny("path_outside_workspace", "scope", resolved=shown)
    if not any(target.is_relative_to(base / root) for root in grant.roots):
        return _deny("path_not_granted", "scope", resolved=shown, roots=list(grant.roots))
    if name == "write_file":
        content = arguments.get("content")
        if not isinstance(content, str):
            return _deny("argument_invalid", "input", reason="content")
        if target.suffix not in WRITE_EXTENSIONS:
            return _deny("extension_not_allowed", "input", resolved=shown, allowed=list(WRITE_EXTENSIONS))
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            return _deny("content_too_large", "input", bytes=len(content.encode("utf-8")), limit=MAX_WRITE_BYTES)
        if SECRET.search(content):
            return _deny("secret_in_payload", "scope", resolved=shown)
    return None


def _check_post(arguments, grant: Grant):
    url, body = arguments.get("url"), arguments.get("body")
    if not isinstance(url, str) or not isinstance(body, str):
        return _deny("argument_invalid", "input", reason="url_or_body")
    host = urlsplit(url).hostname
    if urlsplit(url).scheme != "https" or host not in grant.hosts:
        return _deny("host_not_granted", "scope", host=host or "")
    if SECRET.search(body):
        return _deny("secret_in_payload", "scope", host=host)
    return None


def in_strict_scope(kind: str, target: Path, workspace: Path) -> bool:
    """Whether an effect that really happened is inside what STRICT would have granted.

    Judged from the effect itself (what was touched), not from what the model or a document called it.
    """
    if kind not in ("read", "write"):
        return False  # STRICT grants no outbound tool, so any outbound effect is out of scope
    grant = STRICT.grants["read_file" if kind == "read" else "write_file"]
    base = workspace.resolve()
    return target.is_relative_to(base) and any(target.is_relative_to(base / root) for root in grant.roots)
