"""Isolation helpers for lessons that run commands a model wrote (the coding-agent lessons).

Design, threat model and limits: docs/architecture/sandbox.md. In short:

- ``Workspace``: a throwaway copy of a lesson's fixture repository. It hashes every file
  before and after, so evidence of a change comes from the files, not from the model.
- ``CommandRunner`` and two backends. ``ContainerRunner`` runs each command in a fresh
  docker/podman container without network. ``RestrictedRunner`` runs a local subprocess
  with a cleared environment, a timeout, output limits and process-tree cleanup.
- ``CommandPolicy`` rejects commands that obviously reach outside the workspace or for
  secrets. It reduces accidents. It is not a security boundary: a shell is expressive
  enough to say anything in a way no pattern list anticipates.
- ``run_guarded``: policy first, then human approval when the backend needs it, then the
  runner. Without a working approval channel it refuses (fails closed).

RestrictedRunner is NOT a sandbox. The child runs as the same user, sees the same file
system and network, and can read other same-user processes (for example
/proc/<pid>/environ on Linux). It exists so a learner without a container engine can
still do the lesson, with a human approving every command first.

Text in results is either the command's own output or a stable code (``error_type``,
``rule``). The short English ``error`` strings are for developers; lessons put their
locale text in front of the model with ``CommandResult.to_dict(messages=...)``.
"""
from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import weakref
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping

IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")

BACKEND_RESTRICTED = "restricted"
APPROVAL_EVERY_COMMAND = "every_command"
APPROVAL_NONE = "none"
ApprovalMode = Literal["every_command", "none"]

# A small image with Python is enough for the coding lessons; the image must already be
# present (pulling needs network and time, which a run should not do silently).
DEFAULT_IMAGE = "python:3.12-slim"
MAX_TIMEOUT_SECONDS = 600.0
WORKSPACE_LABEL = "<workspace>"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories and files that tools create as a side effect (bytecode, test caches);
# they are not changes the agent made, so snapshots and diffs skip them.
DEFAULT_IGNORE = ("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache", ".ruff_cache")


class SandboxError(RuntimeError):
    """A sandbox helper could not do what was asked (bad fixture, unusable backend)."""


class BackendUnavailable(SandboxError):
    """The requested backend cannot run here; ``status`` says why."""

    def __init__(self, status: "BackendStatus"):
        super().__init__(f"backend {status.backend} unavailable: {status.reason}")
        self.status = status


# ---------------------------------------------------------------------------
# Workspace: a throwaway copy with before/after evidence
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class FileChange:
    path: str
    status: Literal["added", "removed", "modified"]
    before_sha256: str | None
    after_sha256: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Snapshot:
    """Relative POSIX path -> sha256 of every regular file (symlinks hash their target text)."""
    hashes: dict[str, str]
    truncated: bool = False


class Workspace:
    """A disposable copy of a fixture repository, plus a separate home and temp directory.

    Layout under one temporary directory: ``repo/`` (the copy commands run in),
    ``home/`` and ``tmp/`` (what HOME and TMP point to, so tools that write caches there
    do not touch the learner's real home and do not show up in the diff).

    Use it as a context manager; ``cleanup()`` also runs when the object is collected
    or the interpreter exits, so a crashed run does not leave copies behind for long.
    """

    def __init__(self, source: str | os.PathLike, *, ignore: Iterable[str] = DEFAULT_IGNORE,
                 max_files: int = 5000, max_bytes: int = 50 * 1024 * 1024,
                 keep_text_bytes: int = 512 * 1024, prefix: str = "als-sandbox-"):
        source_path = Path(source)
        if not source_path.is_dir():
            raise SandboxError("fixture source must be an existing directory")
        self.ignore = tuple(ignore)
        self.max_files = max_files
        self.keep_text_bytes = keep_text_bytes
        self._check_fixture(source_path, max_files, max_bytes)
        self.base = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        self._finalizer = weakref.finalize(self, _remove_tree, str(self.base))
        self.root = self.base / "repo"
        self.home = self.base / "home"
        self.tmp = self.base / "tmp"
        try:
            shutil.copytree(source_path, self.root, symlinks=True,
                            ignore=shutil.ignore_patterns(*self.ignore))
            self.home.mkdir()
            self.tmp.mkdir()
        except BaseException:
            self.cleanup()
            raise
        # Baseline: hashes and the text of small files, so a diff never depends on the
        # fixture source staying unchanged while the run goes on.
        self.baseline = self.snapshot()
        self._baseline_bytes: dict[str, bytes] = {}
        for relative in self.baseline.hashes:
            path = self.root / relative
            if not path.is_symlink() and path.stat().st_size <= keep_text_bytes:
                self._baseline_bytes[relative] = path.read_bytes()

    def _check_fixture(self, source: Path, max_files: int, max_bytes: int):
        # A symlink in the fixture would give every command a ready-made way out of the copy.
        files, size = 0, 0
        for directory, dirnames, filenames in os.walk(source):
            dirnames[:] = [name for name in dirnames if not self._ignored(name)]
            for name in dirnames + filenames:
                path = Path(directory) / name
                if path.is_symlink():
                    raise SandboxError(f"fixture contains a symlink: {path.relative_to(source).as_posix()}")
            for name in filenames:
                if self._ignored(name):
                    continue
                files += 1
                size += (Path(directory) / name).stat().st_size
                if files > max_files or size > max_bytes:
                    raise SandboxError("fixture is larger than the workspace limits")

    def _ignored(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, pattern) for pattern in self.ignore)

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *exc_info):
        self.cleanup()

    def cleanup(self):
        """Delete the copy. Idempotent; processes must be gone first (Windows locks open files)."""
        self._finalizer()

    @property
    def closed(self) -> bool:
        return not self._finalizer.alive

    # -- paths -------------------------------------------------------------
    def resolve(self, relative: str) -> Path:
        """Resolve a path the model gave against the workspace; refuse anything that lands outside.

        Symlinks are followed before the check, so a link the agent created cannot be
        used to reach outside either.
        """
        if not isinstance(relative, str) or not relative.strip() or "\x00" in relative:
            raise ValueError("path must be a non-empty string without NUL")
        candidate = Path(relative)
        if candidate.is_absolute() or candidate.drive or relative.startswith(("/", "\\", "~")):
            raise ValueError("path must be relative to the workspace")
        if IS_WINDOWS and ":" in relative:
            # Drive-relative paths (C:foo) and alternate data streams (file:stream).
            raise ValueError("path must not contain ':' on Windows")
        resolved = Path(os.path.realpath(self.root / candidate))
        root = Path(os.path.realpath(self.root))
        if resolved != root and not resolved.is_relative_to(root):
            raise ValueError("path resolves outside the workspace")
        return resolved

    def relative(self, path: Path) -> str:
        return Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(self.root))).as_posix()

    def redact(self, text: str) -> str:
        """Replace local absolute paths of this workspace with labels: events must not carry them."""
        if not text:
            return text
        replacements = []
        # The interpreter directory is on the child's PATH, and tracebacks name the project.
        for path, label in ((self.root, WORKSPACE_LABEL), (self.home, "<home>"), (self.tmp, "<tmp>"),
                            (self.base, "<sandbox>"), (Path(sys.executable).parent, "<python-bin>"),
                            (PROJECT_ROOT, "<project>")):
            for variant in {str(path), os.path.realpath(path), str(path).replace("\\", "/")}:
                replacements.append((variant, label))
        # Longest first, so the repo path is not half-replaced by the base path.
        for variant, label in sorted(replacements, key=lambda item: -len(item[0])):
            if IS_WINDOWS:
                text = re.sub(re.escape(variant), label.replace("\\", "\\\\"), text, flags=re.IGNORECASE)
            else:
                text = text.replace(variant, label)
        return text

    # -- evidence ----------------------------------------------------------
    def snapshot(self) -> Snapshot:
        hashes: dict[str, str] = {}
        truncated = False
        for directory, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = sorted(name for name in dirnames if not self._ignored(name))
            # A symlinked directory is recorded as a link, never walked into.
            for name in list(dirnames):
                if (Path(directory) / name).is_symlink():
                    dirnames.remove(name)
                    filenames.append(name)
            for name in sorted(filenames):
                if self._ignored(name):
                    continue
                path = Path(directory) / name
                relative = path.relative_to(self.root).as_posix()
                if len(hashes) >= self.max_files:
                    truncated = True
                    break
                try:
                    if path.is_symlink():
                        hashes[relative] = "symlink:" + sha256_bytes(os.readlink(path).encode())
                    elif path.is_file():
                        hashes[relative] = sha256_file(path)
                except OSError:
                    hashes[relative] = "unreadable"
        return Snapshot(hashes, truncated)

    def changes(self, after: Snapshot | None = None) -> list[FileChange]:
        after = after or self.snapshot()
        before = self.baseline.hashes
        result = []
        for path in sorted(set(before) | set(after.hashes)):
            old, new = before.get(path), after.hashes.get(path)
            if old == new:
                continue
            status = "added" if old is None else "removed" if new is None else "modified"
            result.append(FileChange(path, status, old, new))
        return result

    def protected_changes(self, patterns: Iterable[str], after: Snapshot | None = None) -> list[FileChange]:
        """Changes to files the agent must not touch (e.g. ``tests/*``), for honest acceptance."""
        patterns = tuple(patterns)
        return [change for change in self.changes(after)
                if any(fnmatch.fnmatch(change.path, pattern) for pattern in patterns)]

    def diff(self, *, max_chars: int = 20000, truncation_marker: str = "\n[... {omitted} chars omitted ...]\n") -> str:
        """Unified diff of every change since the copy was made; binary and large files are named, not shown."""
        parts = []
        for change in self.changes():
            old = self._baseline_bytes.get(change.path) if change.before_sha256 else b""
            new_path = self.root / change.path
            new: bytes | None = b""
            if change.after_sha256:
                new = (None if new_path.is_symlink() or new_path.stat().st_size > self.keep_text_bytes
                       else new_path.read_bytes())
            old_text, new_text = _as_text(old), _as_text(new)
            if old_text is None or new_text is None:
                parts.append(f"Binary or large file {change.status}: {change.path}\n")
                continue
            parts.append("".join(difflib.unified_diff(
                old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile="/dev/null" if change.status == "added" else f"a/{change.path}",
                tofile="/dev/null" if change.status == "removed" else f"b/{change.path}")))
        text = "".join(part if part.endswith("\n") else part + "\n" for part in parts if part)
        if len(text) > max_chars:
            half = max_chars // 2
            text = text[:half] + truncation_marker.format(omitted=len(text) - 2 * half) + text[-half:]
        return text


def _as_text(data: bytes | None) -> str | None:
    if data is None or b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _remove_tree(path: str):
    def make_writable(function, target, _exc):
        # Read-only files (git objects on Windows) refuse deletion until made writable.
        try:
            os.chmod(target, 0o700)
            function(target)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable)
    else:  # pragma: no cover - the project requires 3.12, kept for direct use elsewhere
        shutil.rmtree(path, onerror=make_writable)


# ---------------------------------------------------------------------------
# Results, limits and shells
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OutputLimits:
    """Keep the head and tail of each stream; past ``hard_cap_bytes`` the process tree is killed.

    Head and tail because errors usually show at the start (what failed) and the end
    (the summary); the middle of a long log is what a model can best do without.
    """
    head_bytes: int = 4000
    tail_bytes: int = 4000
    hard_cap_bytes: int = 16 * 1024 * 1024
    marker: str = "\n[... {omitted} bytes omitted ...]\n"


@dataclass(frozen=True)
class ResourceLimits:
    """Best-effort limits for RestrictedRunner; None turns one off.

    POSIX sets them with setrlimit just before exec'ing the shell (macOS: file size only
    in practice; it ignores the address-space limit and the process cap is left off).
    Windows sets them on the job object.
    """
    max_processes: int | None = 256
    memory_bytes: int | None = 2 * 1024 ** 3
    file_size_bytes: int | None = 64 * 1024 ** 2


@dataclass
class CommandResult:
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool
    duration_ms: int
    backend: str
    command: str = ""
    cwd: str = "."
    shell: str | None = None
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    output_limit_exceeded: bool = False
    cancelled: bool = False
    # Pipes still open after the process group was killed: something escaped the cleanup
    # (e.g. a process that called setsid). Reported, because it should not happen silently.
    escaped_processes_suspected: bool = False
    # Resource limits set up for the command. POSIX: requested with setrlimit before exec (a
    # limit the OS refuses is skipped). Windows: job-object limits that were accepted.
    limits_applied: list[str] = field(default_factory=list)
    error_type: str | None = None
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    policy: dict | None = None
    approval: dict | None = None

    @classmethod
    def refused(cls, command: str, backend: str, error_type: str, error: str, **detail) -> "CommandResult":
        """A command that never ran (policy, approval, unusable backend)."""
        return cls(ok=False, exit_code=None, stdout="", stderr="", truncated=False, timed_out=False,
                   duration_ms=0, backend=backend, command=command, error_type=error_type, error=error,
                   detail=detail)

    def to_dict(self, messages: Mapping[str, str] | None = None) -> dict:
        """JSON-ready dict for a tool result or a lesson event.

        ``messages`` maps ``error_type`` (or ``error_type:rule``) to the lesson's locale
        text, formatted with ``detail``; the model then reads the run's language, not
        the developer string.
        """
        data = asdict(self)
        if messages and self.error_type:
            rule = (self.policy or {}).get("rule")
            template = messages.get(f"{self.error_type}:{rule}") or messages.get(self.error_type)
            if template:
                data["error"] = template.format(**self.detail, rule=rule or "")
        return data


@dataclass(frozen=True)
class ShellSpec:
    """How a command string becomes argv: ``argv + [command]``."""
    name: str
    flavor: Literal["posix", "powershell"]
    argv: tuple[str, ...]

    def command_argv(self, command: str) -> list[str]:
        if self.flavor == "powershell":
            # PowerShell 5 writes the console code page by default; force UTF-8 so output decodes.
            command = ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
                       "$OutputEncoding=[System.Text.Encoding]::UTF8;" + command)
        return [*self.argv, command]


def _git_bash() -> str | None:
    """Git for Windows' bash at its install locations; never looked up on PATH."""
    roots = [os.environ.get(name) for name in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)")]
    local = os.environ.get("LOCALAPPDATA")
    candidates = [os.path.join(root, "Git", "bin", "bash.exe") for root in roots if root]
    if local:
        candidates.append(os.path.join(local, "Programs", "Git", "bin", "bash.exe"))
    return next((path for path in candidates if os.path.isfile(path)), None)


def detect_shell(prefer: Literal["posix", "powershell"] = "posix") -> ShellSpec:
    """bash (or sh) on Unix. On Windows: Git Bash when installed and preferred, else PowerShell.

    On Windows ``bash.exe`` found on PATH is often WSL's launcher, which would run the
    command in another operating system with another file system: never pick it.
    """
    if IS_WINDOWS:
        git_bash = _git_bash() if prefer == "posix" else None
        if git_bash:
            return ShellSpec("git-bash", "posix", (git_bash, "-c"))
        for name in ("pwsh", "powershell"):
            path = shutil.which(name)
            if path:
                return ShellSpec(name, "powershell", (path, "-NoLogo", "-NoProfile", "-NonInteractive",
                                                     "-ExecutionPolicy", "Bypass", "-Command"))
        system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        path = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        return ShellSpec("powershell", "powershell", (path, "-NoLogo", "-NoProfile", "-NonInteractive",
                                                     "-ExecutionPolicy", "Bypass", "-Command"))
    bash = shutil.which("bash")
    if bash:
        return ShellSpec("bash", "posix", (bash, "-c"))
    return ShellSpec("sh", "posix", ("/bin/sh", "-c"))


# ---------------------------------------------------------------------------
# Child environment
# ---------------------------------------------------------------------------

POSIX_INHERIT = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM")
# Without SYSTEMROOT, Python and many Windows programs fail at startup (sockets, crypto).
WINDOWS_INHERIT = ("PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
                   "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS", "PSMODULEPATH")
SECRET_NAME = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSW|CREDENTIAL|AUTH|COOKIE|SESSION)")
# A proxy address nothing listens on: cooperative HTTP clients (pip, curl, requests) fail
# fast instead of reaching the network. Raw sockets ignore it; that is what containers are for.
DEAD_PROXY = "http://127.0.0.1:9"


def child_environment(workspace: Workspace, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Start from nothing and add an allowlist: the parent's keys never reach the child."""
    inherit = WINDOWS_INHERIT if IS_WINDOWS else POSIX_INHERIT
    parent = {name.upper(): value for name, value in os.environ.items()} if IS_WINDOWS else os.environ
    env = {name: parent[name] for name in inherit if parent.get(name)}
    # The interpreter running the platform comes first, so `python` in a command is the
    # project's Python even when the server was started without activating the venv.
    python_dir = str(Path(sys.executable).parent)
    default_path = "" if IS_WINDOWS else "/usr/bin:/bin"
    env["PATH"] = os.pathsep.join(part for part in (python_dir, env.get("PATH", default_path)) if part)
    home, tmp = str(workspace.home), str(workspace.tmp)
    env.update({"HOME": home, "TMPDIR": tmp, "TMP": tmp, "TEMP": tmp})
    if IS_WINDOWS:
        env.update({"USERPROFILE": home, "APPDATA": os.path.join(home, "AppData", "Roaming"),
                    "LOCALAPPDATA": os.path.join(home, "AppData", "Local")})
    env.update({
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8", "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "NO_COLOR": "1",
        "http_proxy": DEAD_PROXY, "https_proxy": DEAD_PROXY, "HTTP_PROXY": DEAD_PROXY,
        "HTTPS_PROXY": DEAD_PROXY, "ALL_PROXY": DEAD_PROXY, "all_proxy": DEAD_PROXY,
        "NO_PROXY": "", "no_proxy": "",
    })
    for name, value in (extra or {}).items():
        if SECRET_NAME.search(name):
            raise ValueError(f"refusing to pass a secret-looking variable to a sandboxed command: {name}")
        env[str(name)] = str(value)
    return env


# ---------------------------------------------------------------------------
# Process execution: bounded capture, timeout, tree cleanup
# ---------------------------------------------------------------------------

class _StreamCapture(threading.Thread):
    """Read a pipe to the end, keeping only the head and the tail, and count every byte."""

    def __init__(self, stream, limits: OutputLimits, on_overflow: Callable[[], None]):
        super().__init__(daemon=True)
        self._stream, self._limits, self._on_overflow = stream, limits, on_overflow
        self.head, self.tail, self.total = bytearray(), bytearray(), 0
        self.overflowed = False

    def run(self):
        read = getattr(self._stream, "read1", self._stream.read)
        try:
            while True:
                chunk = read(65536)
                if not chunk:
                    break
                self.total += len(chunk)
                room = self._limits.head_bytes - len(self.head)
                if room > 0:
                    self.head += chunk[:room]
                    chunk = chunk[room:]
                if chunk and self._limits.tail_bytes > 0:
                    self.tail += chunk
                    if len(self.tail) > self._limits.tail_bytes:
                        del self.tail[:-self._limits.tail_bytes]
                if not self.overflowed and self.total > self._limits.hard_cap_bytes:
                    # Keep draining after the kill so the writer is not blocked on a full pipe.
                    self.overflowed = True
                    self._on_overflow()
        except (OSError, ValueError):
            pass

    def text(self, encoding: str = "utf-8") -> tuple[str, bool]:
        kept = len(self.head) + len(self.tail)
        head = bytes(self.head).decode(encoding, errors="replace")
        tail = bytes(self.tail).decode(encoding, errors="replace")
        if self.total <= kept:
            return head + tail, False
        return head + self._limits.marker.format(omitted=self.total - kept) + tail, True


class _ProcessTree:
    """Kill everything a command started, not just the shell.

    POSIX: the shell leads a new session/process group; one killpg reaches every
    descendant that did not leave the group (setsid escapes; the policy denies it,
    the cleanup cannot catch it). Windows: a job object with kill-on-close; taskkill /T
    is the fallback when the job cannot be created.
    """

    def __init__(self, process: subprocess.Popen, resources: ResourceLimits | None):
        self.process = process
        self.applied: list[str] = []
        self._job = None
        if IS_WINDOWS:
            self._job = _WindowsJob.create(process, resources)
            if self._job is not None:
                self.applied.extend(self._job.applied)

    def kill(self):
        if IS_WINDOWS:
            if self._job is not None and self._job.terminate():
                return
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def close(self):
        if self._job is not None:
            self._job.close()


# Runs in place of the shell, sets the limits, then becomes the shell (same pid, so the
# process-group kill still reaches it). Setting them before exec closes the race a
# prlimit() from outside would have: a fast command could finish before the limits land.
_LIMIT_LAUNCHER = """\
import json, os, resource, sys
for name, value in json.loads(sys.argv[1]):
    kind = getattr(resource, name, None)
    if kind is None:
        continue
    try:
        hard = resource.getrlimit(kind)[1]
        if hard != resource.RLIM_INFINITY:
            value = min(value, hard)
        resource.setrlimit(kind, (value, value))
    except (OSError, ValueError):
        pass
os.execv(sys.argv[2], sys.argv[2:])
"""


def _posix_limits(resources: ResourceLimits | None) -> list[tuple[str, int]]:
    if resources is None or IS_WINDOWS:
        return []
    limits = []
    if resources.max_processes is not None and IS_LINUX:
        # RLIMIT_NPROC counts all threads of the real user, not just this tree, so the cap
        # is the current count plus a margin. Root ignores it; macOS counts differently,
        # so it is left off there.
        limits.append(("RLIMIT_NPROC", _linux_user_threads(os.getuid()) + resources.max_processes))
    if resources.memory_bytes is not None:
        limits.append(("RLIMIT_AS", resources.memory_bytes))
    if resources.file_size_bytes is not None:
        limits.append(("RLIMIT_FSIZE", resources.file_size_bytes))
    return limits


def _with_posix_limits(argv: list[str], limits: list[tuple[str, int]]) -> list[str]:
    if not limits:
        return argv
    return [sys.executable, "-I", "-S", "-c", _LIMIT_LAUNCHER, json.dumps(limits), *argv]


def _linux_user_threads(uid: int) -> int:
    count = 0
    try:
        entries = os.scandir("/proc")
    except OSError:
        return 0
    with entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid == uid:
                    count += len(os.listdir(f"/proc/{entry.name}/task"))
            except OSError:
                continue
    return count


class _WindowsJob:
    """Win32 job object via ctypes. Not exercised by the Linux test suite."""

    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    def __init__(self, kernel32, handle, applied):
        self._kernel32, self._handle, self.applied = kernel32, handle, applied

    @classmethod
    def create(cls, process: subprocess.Popen, resources: ResourceLimits | None) -> "_WindowsJob | None":
        try:
            import ctypes
            from ctypes import wintypes

            class IoCounters(ctypes.Structure):
                _fields_ = [(name, ctypes.c_ulonglong) for name in (
                    "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

            class BasicLimits(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class ExtendedLimits(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                         wintypes.DWORD]
            kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel32.CreateJobObjectW(None, None)
            if not handle:
                return None
            info = ExtendedLimits()
            flags = cls.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            applied = ["KILL_ON_JOB_CLOSE"]
            if resources is not None and resources.max_processes is not None:
                flags |= cls.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                info.BasicLimitInformation.ActiveProcessLimit = resources.max_processes
                applied.append("ACTIVE_PROCESS")
            if resources is not None and resources.memory_bytes is not None:
                flags |= cls.JOB_OBJECT_LIMIT_JOB_MEMORY
                info.JobMemoryLimit = resources.memory_bytes
                applied.append("JOB_MEMORY")
            info.BasicLimitInformation.LimitFlags = flags
            if not kernel32.SetInformationJobObject(handle, cls.JobObjectExtendedLimitInformation,
                                                    ctypes.byref(info), ctypes.sizeof(info)):
                kernel32.CloseHandle(handle)
                return None
            # The shell may start a child in the instant before this call; that child would
            # escape the job. taskkill /T in kill() still reaches it through the parent link.
            if not kernel32.AssignProcessToJobObject(handle, int(process._handle)):
                kernel32.CloseHandle(handle)
                return None
            return cls(kernel32, handle, applied)
        except (OSError, AttributeError, ImportError):
            return None

    def terminate(self) -> bool:
        return bool(self._handle) and bool(self._kernel32.TerminateJobObject(self._handle, 1))

    def close(self):
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def _exited(process: subprocess.Popen) -> bool:
    """True once the process has exited; on POSIX it is left unreaped (a zombie).

    Not reaping keeps the pid, and so the process-group id, reserved until killpg has
    run: a recycled pid could otherwise make the cleanup signal an unrelated group.
    """
    if process.returncode is not None:
        return True
    if not IS_WINDOWS and hasattr(os, "waitid"):
        try:
            info = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            process.poll()
            return True
        return info is not None and info.si_pid != 0
    return process.poll() is not None


@dataclass
class _Outcome:
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool
    cancelled: bool
    output_limit_exceeded: bool
    escaped: bool
    duration_ms: int
    stdout_bytes: int
    stderr_bytes: int
    limits_applied: list[str]


def _run_process(argv: list[str], *, cwd: str | None, env: dict[str, str] | None, timeout: float,
                 output: OutputLimits, resources: ResourceLimits | None,
                 should_stop: Callable[[], bool] | None, on_kill: Callable[[], None] | None = None,
                 encoding: str = "utf-8") -> _Outcome:
    kwargs: dict[str, Any] = {"cwd": cwd, "env": env, "stdin": subprocess.DEVNULL,
                              "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    started = time.perf_counter()
    process = subprocess.Popen(argv, **kwargs)
    tree = _ProcessTree(process, resources)
    overflow = threading.Event()
    captures = [_StreamCapture(process.stdout, output, overflow.set),
                _StreamCapture(process.stderr, output, overflow.set)]
    for capture in captures:
        capture.start()
    deadline = started + timeout
    timed_out = cancelled = False
    delay = 0.005
    try:
        while not _exited(process):
            if overflow.is_set():
                break
            if should_stop is not None and should_stop():
                cancelled = True
                break
            if time.perf_counter() >= deadline:
                timed_out = True
                break
            time.sleep(delay)
            delay = min(delay * 2, 0.05)
        duration_ms = round((time.perf_counter() - started) * 1000)
    finally:
        # Always, even after a normal exit: background children of the command must not
        # outlive it (and would keep the pipes open).
        if on_kill is not None and (timed_out or cancelled or overflow.is_set()):
            on_kill()
        tree.kill()
        process.wait()
        tree.close()
    escaped = False
    for capture in captures:
        capture.join(timeout=2.0)
        escaped = escaped or capture.is_alive()
    if not escaped:
        process.stdout.close()
        process.stderr.close()
    stdout, stdout_cut = captures[0].text(encoding)
    stderr, stderr_cut = captures[1].text(encoding)
    return _Outcome(process.returncode, stdout, stderr, stdout_cut or stderr_cut, timed_out, cancelled,
                    overflow.is_set(), escaped, duration_ms, captures[0].total, captures[1].total,
                    tree.applied)


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BackendStatus:
    backend: str
    available: bool
    reason: str  # ok | engine_not_found | engine_unreachable | image_missing | probe_failed
    engine: str | None = None
    version: str | None = None
    image: str | None = None
    message: str = ""
    checked: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class CommandRunner(ABC):
    """Run one command string in a workspace and return a CommandResult, never raise for the command's own failure."""
    backend: str
    isolated: bool  # True only when the backend is a real isolation boundary

    def __init__(self, workspace: Workspace, *, timeout: float = 30.0, output: OutputLimits = OutputLimits()):
        _check_timeout(timeout)
        self.workspace, self.timeout, self.output = workspace, float(timeout), output

    @property
    @abstractmethod
    def shell_flavor(self) -> Literal["posix", "powershell"]:
        """The shell syntax commands are written in; the system prompt should say it."""

    @abstractmethod
    def run(self, command: str, *, timeout: float | None = None,
            should_stop: Callable[[], bool] | None = None) -> CommandResult:
        ...

    def _prepare(self, command: str, timeout: float | None) -> float:
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        if self.workspace.closed:
            raise SandboxError("workspace was already cleaned up")
        timeout = self.timeout if timeout is None else timeout
        _check_timeout(timeout)
        return float(timeout)

    def _result(self, command: str, outcome: _Outcome, shell: str) -> CommandResult:
        error_type = error = None
        if outcome.cancelled:
            error_type, error = "cancelled", "the run was stopped while the command was running"
        elif outcome.timed_out:
            error_type, error = "timeout", "the command exceeded its timeout; its process tree was killed"
        elif outcome.output_limit_exceeded:
            error_type, error = "output_limit", "the command wrote more output than allowed; it was killed"
        elif outcome.exit_code != 0:
            error_type, error = "nonzero_exit", f"exit code {outcome.exit_code}"
        redact = self.workspace.redact
        return CommandResult(
            ok=error_type is None, exit_code=outcome.exit_code, stdout=redact(outcome.stdout),
            stderr=redact(outcome.stderr), truncated=outcome.truncated, timed_out=outcome.timed_out,
            duration_ms=outcome.duration_ms, backend=self.backend, command=command, shell=shell,
            stdout_bytes=outcome.stdout_bytes, stderr_bytes=outcome.stderr_bytes,
            output_limit_exceeded=outcome.output_limit_exceeded, cancelled=outcome.cancelled,
            escaped_processes_suspected=outcome.escaped, limits_applied=list(outcome.limits_applied),
            error_type=error_type, error=error,
            detail={"exit_code": outcome.exit_code} if error_type == "nonzero_exit" else {})


def _check_timeout(timeout: float):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout must be a number of seconds in (0, {MAX_TIMEOUT_SECONDS:g}]")


class RestrictedRunner(CommandRunner):
    """Local subprocess with guard rails. NOT a sandbox: same user, same file system, same network.

    What it does: cwd fixed to the workspace copy, environment built from an allowlist,
    stdin closed, timeout, head/tail output limits, and the whole process tree killed
    after every command (so nothing keeps running in the background).
    """
    backend = BACKEND_RESTRICTED
    isolated = False

    def __init__(self, workspace: Workspace, *, timeout: float = 30.0, output: OutputLimits = OutputLimits(),
                 resources: ResourceLimits | None = ResourceLimits(), shell: ShellSpec | None = None,
                 env_extra: Mapping[str, str] | None = None):
        super().__init__(workspace, timeout=timeout, output=output)
        self.resources = resources
        self.shell = shell or detect_shell()
        self.env = child_environment(workspace, env_extra)

    @property
    def shell_flavor(self):
        return self.shell.flavor

    def run(self, command, *, timeout=None, should_stop=None):
        timeout = self._prepare(command, timeout)
        limits = _posix_limits(self.resources)
        try:
            outcome = _run_process(_with_posix_limits(self.shell.command_argv(command), limits),
                                   cwd=str(self.workspace.root), env=self.env, timeout=timeout,
                                   output=self.output, resources=self.resources, should_stop=should_stop)
        except OSError as error:
            return CommandResult.refused(command, self.backend, "spawn_failed",
                                         f"could not start the shell: {type(error).__name__}")
        result = self._result(command, outcome, self.shell.name)
        result.limits_applied = [name for name, _ in limits] + result.limits_applied
        if result.error_type == "timeout":
            result.detail = {"timeout_s": timeout}
        return result


class ContainerRunner(CommandRunner):
    """One fresh container per command: no network, read-only root, capped memory and processes.

    Only the workspace copy is mounted (read-write at /workspace); nothing from the
    host environment is passed in except the variables set here. One container per
    command keeps runs independent; the cost is about a second of start-up each time.
    """
    isolated = True

    def __init__(self, workspace: Workspace, *, engine: str | None = None, image: str = DEFAULT_IMAGE,
                 timeout: float = 30.0, output: OutputLimits = OutputLimits(), memory: str = "1g",
                 cpus: str = "1", pids_limit: int = 128, shell: tuple[str, ...] = ("sh", "-c")):
        super().__init__(workspace, timeout=timeout, output=output)
        if engine is None:
            status = self.detect(image=image)
            if not status.available:
                raise BackendUnavailable(status)
            engine = status.engine
        self.engine = engine
        self.engine_name = Path(engine).stem.lower()
        self.backend = f"container:{self.engine_name}"
        self.image, self.memory, self.cpus, self.pids_limit, self.shell = image, memory, cpus, pids_limit, shell

    @property
    def shell_flavor(self):
        return "posix"

    @staticmethod
    def detect(*, image: str = DEFAULT_IMAGE, engines: Iterable[str] = ("docker", "podman"),
               timeout: float = 10.0) -> BackendStatus:
        """Find a container engine that answers and already has ``image``. Never pulls."""
        checked = []
        first_failure: BackendStatus | None = None
        for name in engines:
            path = shutil.which(name)
            if not path:
                checked.append(f"{name}:engine_not_found")
                continue
            probe = ([path, "info", "--format", "{{.Version.Version}}"] if name == "podman"
                     else [path, "version", "--format", "{{.Server.Version}}"])
            try:
                answer = subprocess.run(probe, capture_output=True, text=True, timeout=timeout, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                checked.append(f"{name}:probe_failed")
                first_failure = first_failure or BackendStatus(
                    f"container:{name}", False, "probe_failed", engine=path, image=image,
                    message=type(error).__name__)
                continue
            if answer.returncode != 0:
                checked.append(f"{name}:engine_unreachable")
                first_failure = first_failure or BackendStatus(
                    f"container:{name}", False, "engine_unreachable", engine=path, image=image,
                    message=_first_line(answer.stderr))
                continue
            version = answer.stdout.strip() or None
            try:
                found = subprocess.run([path, "image", "inspect", image], capture_output=True, text=True,
                                       timeout=timeout, check=False)
            except (OSError, subprocess.TimeoutExpired):
                found = None
            if found is None or found.returncode != 0:
                checked.append(f"{name}:image_missing")
                first_failure = first_failure or BackendStatus(
                    f"container:{name}", False, "image_missing", engine=path, version=version, image=image,
                    message=f"run `{name} pull {image}` once, then restart the run")
                continue
            checked.append(f"{name}:ok")
            return BackendStatus(f"container:{name}", True, "ok", engine=path, version=version, image=image,
                                 checked=tuple(checked))
        if first_failure is not None:
            return replace(first_failure, checked=tuple(checked))
        return BackendStatus("container", False, "engine_not_found", image=image, checked=tuple(checked),
                             message="neither docker nor podman is on PATH")

    def build_argv(self, command: str, name: str) -> list[str]:
        argv = [self.engine, "run", "--rm", "--name", name, "--init",
                "--network", "none", "--memory", self.memory, "--memory-swap", self.memory,
                "--cpus", self.cpus, "--pids-limit", str(self.pids_limit),
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--read-only", "--tmpfs", "/tmp:rw,size=256m",
                "--mount", f"type=bind,source={self.workspace.root},target=/workspace",
                "--workdir", "/workspace"]
        if IS_LINUX and self.engine_name == "podman":
            argv += ["--userns", "keep-id"]
        elif IS_LINUX:
            # Files the agent writes stay owned by the learner, so cleanup can delete them.
            argv += ["--user", f"{os.getuid()}:{os.getgid()}"]
        for key, value in (("HOME", "/tmp"), ("PYTHONDONTWRITEBYTECODE", "1"), ("PYTHONUTF8", "1"),
                           ("PIP_NO_INDEX", "1"), ("NO_COLOR", "1")):
            argv += ["--env", f"{key}={value}"]
        return [*argv, self.image, *self.shell, command]

    def run(self, command, *, timeout=None, should_stop=None):
        timeout = self._prepare(command, timeout)
        name = f"als-sandbox-{uuid.uuid4().hex[:12]}"

        def kill_container():
            # Killing the CLI does not stop the container; ask the engine directly.
            subprocess.run([self.engine, "kill", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, check=False)
            subprocess.run([self.engine, "rm", "-f", name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15, check=False)

        try:
            # The CLI itself is trusted platform code and gets the normal environment
            # (DOCKER_HOST, contexts); the container only gets the --env entries above.
            outcome = _run_process(self.build_argv(command, name), cwd=None, env=None, timeout=timeout,
                                   output=self.output, resources=None, should_stop=should_stop,
                                   on_kill=kill_container)
        except OSError as error:
            return CommandResult.refused(command, self.backend, "spawn_failed",
                                         f"could not start the container engine: {type(error).__name__}")
        result = self._result(command, outcome, " ".join(self.shell))
        if result.error_type == "timeout":
            result.detail = {"timeout_s": timeout}
        return result


def _first_line(text: str) -> str:
    return (text or "").strip().splitlines()[0][:200] if (text or "").strip() else ""


def select_runner(workspace: Workspace, *, prefer: Literal["auto", "container", "restricted"] = "auto",
                  image: str = DEFAULT_IMAGE, timeout: float = 30.0, output: OutputLimits = OutputLimits(),
                  container_options: Mapping[str, Any] | None = None,
                  restricted_options: Mapping[str, Any] | None = None) -> tuple[CommandRunner, BackendStatus]:
    """Pick the backend: a container when one is usable, otherwise the restricted runner.

    The returned status says what was found, so the lesson can show the learner why it
    is running without a container (and that every command will need approval).
    """
    if prefer not in ("auto", "container", "restricted"):
        raise ValueError("prefer must be auto, container or restricted")
    if prefer != "restricted":
        status = ContainerRunner.detect(image=image)
        if status.available:
            return ContainerRunner(workspace, engine=status.engine, image=image, timeout=timeout,
                                   output=output, **dict(container_options or {})), status
        if prefer == "container":
            raise BackendUnavailable(status)
    else:
        status = BackendStatus(BACKEND_RESTRICTED, True, "ok", message="restricted runner requested")
    return RestrictedRunner(workspace, timeout=timeout, output=output, **dict(restricted_options or {})), status


def default_approval_mode(runner: CommandRunner) -> ApprovalMode:
    """Without an isolation boundary a human approves every command; inside a container none is needed."""
    return APPROVAL_NONE if runner.isolated else APPROVAL_EVERY_COMMAND


# ---------------------------------------------------------------------------
# Command policy: fewer accidents, not a boundary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyDecision:
    action: Literal["allow", "deny"]
    rule: str | None = None
    matched: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# A command word: at the start, or after ; & | ( ` $( or a newline.
_CMD = r"(?:^|[;&|(`\n]|\$\()\s*"
_END = r"(?:\.exe)?(?=$|[\s;&|)`])"
_SEP = r"(?:^|[\s\"'=(,;|&<>:/\\])"

_RULES: tuple[tuple[str, str, re.Pattern], ...] = tuple(
    (rule, flavors, re.compile(pattern, flags)) for rule, flavors, pattern, flags in (
        ("fork_bomb", "*", r":\s*\(\s*\)\s*\{|%0\s*\|\s*%0|\bos\.fork\b|\bfork\s*\(\s*\)", 0),
        ("privilege", "*", _CMD + r"(sudo|su|doas|runas|pkexec)" + _END + r"|-Verb\s+RunAs", re.I),
        ("system_control", "*", _CMD + r"(shutdown|reboot|halt|poweroff|mkfs(\.\w+)?|fdisk|parted|diskpart|"
         r"systemctl|launchctl|crontab|schtasks|bcdedit|mount|umount|chroot|reg|Stop-Computer|"
         r"Restart-Computer|Set-ExecutionPolicy)" + _END + r"|\bgit\s+config\s+--(global|system)\b|"
         r"\bdd\s[^;&|\n]*\b(if|of)=", re.I),
        ("process_control", "*", _CMD + r"(kill|killall|pkill|taskkill|Stop-Process|spps)" + _END, re.I),
        ("secret_file", "*", r"local_config|" + _SEP + r"\.env(\.[\w-]+)?(?=$|[\s\"';|&<>)])|\.ssh\b|"
         r"\bid_(rsa|dsa|ecdsa|ed25519)\b|\.aws\b|\.azure\b|gcloud|\.netrc\b|_netrc\b|\.pgpass\b|"
         r"\.git-credentials|\.npmrc\b|\.pypirc\b|\.docker[/\\]config|\.kube\b|credentials\.json", re.I),
        ("secret_env", "*", r"(\$\{?|%|\$env:|getenv\(\s*['\"]?|environ\[\s*['\"]|environ\.get\(\s*['\"])"
         r"\w*(KEY|SECRET|TOKEN|PASSW|CREDENTIAL)|\b[A-Z][A-Z0-9_]*_(API_KEY|SECRET|TOKEN|ACCESS_KEY)\b", re.I),
        ("environment_dump", "*", r"/proc/[^\s/]+/(environ|cmdline|mem|maps)|" + _CMD +
         r"(printenv|env|set|export\s+-p|declare\s+-x)(?=$|[\s;&|)`])(?!\s*[A-Za-z_]+=)(?!\s+-)|"
         r"\b(Get-ChildItem|gci|dir|ls|Get-Item)\s+env:|GetEnvironmentVariables|"
         r"\bos\.environ\b(?!\s*\[\s*['\"](PATH|HOME|PWD)['\"])", re.I),
        ("network", "*", _CMD + r"(curl|wget|nc|ncat|netcat|socat|telnet|ssh|scp|sftp|rsync|ftp|tftp|"
         r"Invoke-WebRequest|Invoke-RestMethod|iwr|irm|Test-NetConnection|Start-BitsTransfer|bitsadmin|"
         r"certutil)" + _END + r"|\bgit\s+(clone|fetch|pull|push|remote|submodule|ls-remote)\b|"
         r"\b(import|from)\s+(urllib|requests|httpx|aiohttp|socket|http\.client|ftplib|smtplib)\b|"
         r"\b(https?|ftp)://", re.I),
        ("package_install", "*", _CMD + r"(pip3?|uv|poetry|pipx|conda|mamba|npm|pnpm|yarn|apt|apt-get|yum|"
         r"dnf|apk|brew|choco|winget|scoop|gem|cargo|go)" + r"\s+(install|add|i|update|upgrade|remove|"
         r"uninstall|get|sync)\b|-m\s+(pip|ensurepip)\b|\b(Install-Module|Install-Package)\b", re.I),
        ("background_process", "posix", _CMD + r"(nohup|setsid|disown|screen|tmux|daemonize|at|batch)"
         + _END + r"|(?<![&|><0-9])&(?![&>])", 0),
        ("background_process", "powershell", r"\b(Start-Job|Start-Process|Start-ThreadJob|saps|"
         r"Register-ScheduledJob|Register-ScheduledTask)\b|\bnohup\b|\bsetsid\b", re.I),
        ("obfuscation", "*", _CMD + r"eval" + _END + r"|\|\s*(sudo\s+)?(sh|bash|zsh|dash|ksh|fish|pwsh|"
         r"powershell|cmd)(\.exe)?\b|\bbase64\s+(-d|--decode|-D)\b|\bxxd\s+-r\b|"
         r"\b(Invoke-Expression|iex)\b|FromBase64String|"
         r"\b(powershell|pwsh)(\.exe)?\b[^;&|\n]*\s-(e|ec|enc|encodedcommand)\b|"
         r"(?<![.\w])(exec|eval|compile|__import__)\s*\(", re.I),
        ("parent_traversal", "*", _SEP + r"\.\.(?=$|[/\\\s\"';|&<>)])", 0),
        ("home_path", "*", r"(?:^|[\s\"'=(,;|&<>])~(?=$|[/\\\s\"';|&<>)\w])|\$HOME\b|\$\{HOME\}|"
         r"%USERPROFILE%|\$env:USERPROFILE", re.I),
        ("absolute_path", "*", r"(?:^|[\s\"'=(,;|&<>])([a-z]:[\\/]|\\\\[^\s\\]+)", re.I),
    ))

_SLASH_WORD = re.compile(r"(?:^|(?<=[\s\"'=(,;|&<>:]))(/[^\s\"';|&<>)`]*)")
_ALLOWED_ABSOLUTE = {"/dev/null", "/dev/stdout", "/dev/stderr"}


class CommandPolicy:
    """Deny commands that obviously leave the workspace or go for secrets.

    Pattern rules over the raw command string, in the order of ``_RULES``. Anyone who
    wants to get past them can (``$(printf 'c\\x75rl')``, a Python script written to a
    file first, ...). Their job is to stop the common accidents and make the model
    rephrase; the isolation, if any, comes from the backend.
    """
    MAX_COMMAND_CHARS = 4000

    def __init__(self, flavor: Literal["posix", "powershell"] = "posix", *,
                 root_entries: Iterable[str] | None = None):
        if flavor not in ("posix", "powershell"):
            raise ValueError("flavor must be posix or powershell")
        self.flavor = flavor
        self._root_entries = {name.lower() for name in (root_entries if root_entries is not None
                                                         else _host_root_entries())}

    @classmethod
    def for_runner(cls, runner: CommandRunner) -> "CommandPolicy":
        return cls(runner.shell_flavor)

    def evaluate(self, command: str) -> PolicyDecision:
        if not isinstance(command, str) or not command.strip():
            return PolicyDecision("deny", "empty_command")
        if len(command) > self.MAX_COMMAND_CHARS:
            return PolicyDecision("deny", "command_too_long", f"{len(command)} chars")
        if re.search(r"[\x00-\x08\x0b-\x1f\x7f]", command.replace("\r\n", "\n")):
            return PolicyDecision("deny", "control_characters")
        for rule, flavors, pattern in _RULES:
            if flavors not in ("*", self.flavor):
                continue
            match = pattern.search(command)
            if match:
                return PolicyDecision("deny", rule, _excerpt(match.group(0)))
        for match in _SLASH_WORD.finditer(command):
            word = match.group(1)
            if word in _ALLOWED_ABSOLUTE:
                continue
            first = word.strip("/").split("/", 1)[0].lower()
            # "/" alone, or a path whose first segment exists at the host's root, is a real
            # absolute path. "/foo/" in a sed or awk pattern usually is not.
            # A bare "/" right after ":" is a sed or awk delimiter ('s/a:/b:/'), not the root directory.
            after_colon = match.start(1) > 0 and command[match.start(1) - 1] == ":"
            if (not first and not after_colon) or first in self._root_entries:
                return PolicyDecision("deny", "absolute_path", _excerpt(word))
        return PolicyDecision("allow")


def _excerpt(text: str, limit: int = 80) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _host_root_entries() -> list[str]:
    root = (os.environ.get("SYSTEMDRIVE", "C:") + "\\") if IS_WINDOWS else "/"
    try:
        return os.listdir(root)
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Approval and the guarded entry point
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApprovalRequest:
    """What a human sees before a command runs. ``command`` is exactly the string that will run."""
    command: str
    backend: str
    isolated: bool
    timeout_s: float
    policy: dict
    cwd: str = WORKSPACE_LABEL
    tool: str = "bash"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalOutcome:
    """How one approval ended. ``command`` is the approved text when the human edited it."""
    approved: bool
    note: str | None = None
    outcome: str | None = None  # approved | rejected | timeout, when the channel reports it
    command: str | None = None
    approval_id: str | None = None
    decided_by: str | None = None

    def to_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if key != "command"}


# The approval channel a lesson passes in. It may block until a human answers and may raise
# RunCancelled. It returns a bool, {"decision": "approve"|"reject", "note": ...}, an
# ApprovalOutcome, or the platform's ApprovalDecision (see context_approver).
Approver = Callable[[ApprovalRequest], Any]


def _normalize_approval(answer: Any) -> ApprovalOutcome:
    if isinstance(answer, ApprovalOutcome):
        return answer
    if isinstance(answer, bool):
        return ApprovalOutcome(answer)
    if isinstance(answer, Mapping):
        decision = answer.get("decision")
        if decision not in ("approve", "reject"):
            raise ValueError("approval decision must be 'approve' or 'reject'")
        return ApprovalOutcome(decision == "approve", answer.get("note"))
    if hasattr(answer, "approved"):
        # RunContext.request_approval's ApprovalDecision: its payload is what was approved,
        # possibly edited, so the command to run is read back from it.
        payload = getattr(answer, "payload", None)
        command = payload.get("command") if isinstance(payload, Mapping) else None
        if command is not None and not isinstance(command, str):
            raise ValueError("an approved payload must carry the command as a string")
        return ApprovalOutcome(bool(answer.approved), getattr(answer, "note", None),
                               getattr(answer, "outcome", None), command,
                               getattr(answer, "approval_id", None), getattr(answer, "decided_by", None))
    raise TypeError("an approver must return a bool, a decision mapping or an object with 'approved'")


def context_approver(context: Any, summary: Callable[[ApprovalRequest], str], *, risk: str = "high",
                     timeout_s: float = 300, editable: bool = False, kind: str = "command") -> Approver:
    """Adapt ``RunContext.request_approval`` for run_guarded.

    ``summary`` builds the one-line text the learner reads, in the run's language (lesson
    locales); the payload is ``ApprovalRequest.to_dict()``, so the exact command, backend
    and ``isolated`` flag are on record in approval_requested. With ``editable=True`` an
    edited command is policy-checked again before it runs.
    """
    def approve(request: ApprovalRequest):
        return context.request_approval(kind, summary(request), request.to_dict(), timeout_s=timeout_s,
                                        risk=risk, editable=editable)
    return approve


def run_guarded(command: str, *, runner: CommandRunner, policy: CommandPolicy | None = None,
                approve: Approver | None = None, approval_mode: ApprovalMode | None = None,
                timeout: float | None = None, should_stop: Callable[[], bool] | None = None,
                check_cancelled: Callable[[], None] | None = None) -> CommandResult:
    """Policy, then approval when required, then the runner; the result says which step decided.

    ``approval_mode`` defaults to ``default_approval_mode(runner)``: every command for the
    restricted runner. A required approval with no ``approve`` channel is refused
    (``approval_unavailable``): no channel never means "approved".
    """
    policy = policy or CommandPolicy.for_runner(runner)
    mode = approval_mode or default_approval_mode(runner)
    if mode not in (APPROVAL_EVERY_COMMAND, APPROVAL_NONE):
        raise ValueError("approval_mode must be every_command or none")
    if check_cancelled is not None:
        check_cancelled()
    decision = policy.evaluate(command)
    if decision.action == "deny":
        result = CommandResult.refused(command, runner.backend, "policy_denied",
                                       f"command refused by policy rule {decision.rule}",
                                       matched=decision.matched or "")
        result.policy = decision.to_dict()
        return result
    approval = record = None
    if mode == APPROVAL_EVERY_COMMAND:
        effective_timeout = runner.timeout if timeout is None else timeout
        request = ApprovalRequest(command=command, backend=runner.backend, isolated=runner.isolated,
                                  timeout_s=float(effective_timeout), policy=decision.to_dict())
        if approve is None:
            result = CommandResult.refused(command, runner.backend, "approval_unavailable",
                                           "this backend needs human approval and no approval channel was given")
            result.policy = decision.to_dict()
            return result
        approval = _normalize_approval(approve(request))
        record = {"required": True, **approval.to_dict()}
        if not approval.approved:
            timed_out = approval.outcome == "timeout"
            result = CommandResult.refused(
                command, runner.backend, "approval_timeout" if timed_out else "approval_rejected",
                "nobody decided in time" if timed_out else "a human rejected the command",
                note=approval.note or "")
            result.policy, result.approval = decision.to_dict(), record
            return result
        if approval.command is not None and approval.command != command:
            # The human approved an edited command: that text runs, after its own policy check.
            record["edited"] = True
            command = approval.command
            decision = policy.evaluate(command)
            if decision.action == "deny":
                result = CommandResult.refused(command, runner.backend, "policy_denied",
                                               f"command refused by policy rule {decision.rule}",
                                               matched=decision.matched or "")
                result.policy, result.approval = decision.to_dict(), record
                return result
        if check_cancelled is not None:
            check_cancelled()
    result = runner.run(command, timeout=timeout, should_stop=should_stop)
    result.policy = decision.to_dict()
    result.approval = record if approval else {"required": False}
    return result


__all__ = [
    "APPROVAL_EVERY_COMMAND", "APPROVAL_NONE", "ApprovalOutcome", "ApprovalRequest", "Approver",
    "BACKEND_RESTRICTED", "BackendStatus", "BackendUnavailable", "CommandPolicy", "CommandResult",
    "CommandRunner", "ContainerRunner", "DEFAULT_IMAGE", "FileChange", "OutputLimits", "PolicyDecision",
    "ResourceLimits", "RestrictedRunner", "SandboxError", "ShellSpec", "Snapshot", "Workspace",
    "child_environment", "context_approver", "default_approval_mode", "detect_shell", "run_guarded", "select_runner",
    "sha256_file",
]
