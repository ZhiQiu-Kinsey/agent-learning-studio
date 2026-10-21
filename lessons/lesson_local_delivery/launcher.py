"""The launcher side of delivery: start the app as a child process, wait for it, probe it, stop it, prove it is gone.

Everything here talks to a real process over a real socket. Nothing is simulated: a fault is a flag the
app really obeys, a timeout is a clock that really ran out, "gone" is a pid that really no longer exists.
"""
import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from lessons.lesson_local_delivery.settings import ENV_PREFIX

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODULE = "lessons.lesson_local_delivery.notes_app"
# What a child may inherit. Provider keys, tokens and the rest of this process's environment stay behind:
# the app gets exactly the NOTES_* values the check hands it, which is also what "empty environment" means.
INHERITED = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")
POLL_SECONDS = 0.05
PROBE_TIMEOUT = 0.5


def child_environment(extra: dict[str, str]) -> dict[str, str]:
    environment = {name: os.environ[name] for name in INHERITED if name in os.environ}
    environment.update(extra)
    return environment


def pid_alive(pid: int) -> bool:
    """True while the process exists and has not become a zombie (a killed orphan nobody has waited for)."""
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT: still running
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # signal 0 checks existence without touching the process
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        # In a container nobody may reap an orphan: it stays in the table as a zombie, which is dead for our purpose.
        with open(f"/proc/{pid}/stat", encoding="ascii") as stat:
            return stat.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def wait_gone(pids: list[int], timeout: float = 3.0) -> list[int]:
    """The pids still running after ``timeout`` seconds; empty means every one of them exited."""
    deadline = time.monotonic() + timeout
    alive = [pid for pid in pids if pid_alive(pid)]
    while alive and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        alive = [pid for pid in alive if pid_alive(pid)]
    return alive


def port_accepts(port: int) -> bool:
    """Does anything still accept a connection on this loopback port?"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def other_interface_address() -> str | None:
    """An address of this machine that is not loopback, or None when there is no network at all.

    A UDP connect sends no packet: it only asks the routing table which local address would be used.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1: reserved, never routed to a real host
            address = probe.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith("127.") or address == "0.0.0.0" else address


@dataclass
class Probe:
    endpoint: str
    status: int | None  # None: the connection itself failed
    body: dict | None
    elapsed_ms: float
    text: str = ""  # the response exactly as received, so a check can scan it for a credential
    at_ms: float = 0.0  # when the probe was sent, counted from the moment the process was started


def http_probe(port: int, method: str, path: str, payload: dict | None = None, host: str = "127.0.0.1") -> Probe:
    started = time.perf_counter()
    status, body, text = None, None, ""
    connection = http.client.HTTPConnection(host, port, timeout=PROBE_TIMEOUT)
    try:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        connection.request(method, path, body=data, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        status = response.status
        text = response.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except ValueError:
            body = None
    except (OSError, http.client.HTTPException):
        pass
    finally:
        connection.close()
    return Probe(f"{method} {path}", status, body, round((time.perf_counter() - started) * 1000, 1), text)


@dataclass
class Listening:
    state: str  # listening | exited | timeout
    elapsed_ms: float
    port: int | None = None
    exit_code: int | None = None


@dataclass
class Waited:
    state: str  # ready | not_ready | exited
    elapsed_ms: float
    probes: list[Probe] = field(default_factory=list)


@dataclass
class Stopped:
    method: str  # graceful | terminated | killed | already_exited
    exit_code: int | None
    elapsed_ms: float


class AppProcess:
    """One run of the app. Used as a context manager so the whole process group is gone when the block ends."""

    def __init__(self, workdir: Path, env: dict[str, str], *, config: str | None = None, warmup_ms: int = 400,
                 fault: str = "none", name: str = "app"):
        self.workdir, self.env, self.config = workdir, env, config
        self.warmup_ms, self.fault, self.name = warmup_ms, fault, name
        self.port_file = workdir / f"{name}.port"
        self.log_path = workdir / f"{name}.log"
        self.process: subprocess.Popen | None = None
        self.port: int | None = None
        self.worker_pid: int | None = None
        self.pids: list[int] = []
        self.started_at = 0.0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.reap()

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    def start(self) -> None:
        self.port_file.unlink(missing_ok=True)
        command = [sys.executable, "-m", MODULE, "--workdir", str(self.workdir), "--port-file", str(self.port_file),
                   "--warmup-ms", str(self.warmup_ms), "--fault", self.fault]
        if self.config:
            command += ["--config", self.config]
        # A new session makes the app the leader of its own process group, so one signal can reach its worker too.
        flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
            else {"start_new_session": True}
        self.started_at = time.perf_counter()
        with open(self.log_path, "ab") as log:  # the app's stderr: JSON log lines
            self.process = subprocess.Popen(command, cwd=str(REPOSITORY_ROOT), env=child_environment(self.env),
                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, **flags)
        self.pids = [self.process.pid]

    def _elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 1)

    def wait_listening(self, timeout_s: float, check: Callable[[], None]) -> Listening:
        """Wait for the port file. The app writes it only after the socket listens; an early exit ends the wait."""
        deadline = time.monotonic() + timeout_s
        while True:
            check()
            if self.port_file.exists():
                text = self.port_file.read_text(encoding="ascii").strip()
                if text.isdigit():
                    self.port = int(text)
                    return Listening("listening", self._elapsed_ms(), port=self.port)
            code = self.process.poll()
            if code is not None:
                return Listening("exited", self._elapsed_ms(), exit_code=code)
            if time.monotonic() >= deadline:
                return Listening("timeout", self._elapsed_ms())
            time.sleep(POLL_SECONDS)

    def wait_ready(self, timeout_s: float, check: Callable[[], None]) -> Waited:
        """Probe /health and /ready until /ready answers 200, the limit passes or the process exits.

        Only changes are kept: a probe whose endpoint and status equal the previous probe of that endpoint adds nothing.
        """
        deadline = time.monotonic() + timeout_s
        kept: list[Probe] = []
        last: dict[str, int | None] = {}
        while True:
            check()
            for path in ("/health", "/ready"):
                probe = http_probe(self.port, "GET", path)
                probe.at_ms = self._elapsed_ms()
                if probe.status != last.get(path, -1):
                    kept.append(probe)
                last[path] = probe.status
                if path == "/health" and probe.body:
                    self.worker_pid = probe.body.get("worker_pid")
                    if self.worker_pid and self.worker_pid not in self.pids:
                        self.pids.append(self.worker_pid)
                if path == "/ready" and probe.status == 200:
                    return Waited("ready", self._elapsed_ms(), kept)
            if self.process.poll() is not None:
                return Waited("exited", self._elapsed_ms(), kept)
            if time.monotonic() >= deadline:
                return Waited("not_ready", self._elapsed_ms(), kept)
            time.sleep(POLL_SECONDS)

    def note_worker(self, timeout_s: float = 1.0) -> None:
        """Learn the worker's pid from /health. The app opens its port a moment before it starts the worker, so ask again."""
        deadline = time.monotonic() + timeout_s
        while self.port and self.worker_pid is None and time.monotonic() < deadline:
            probe = http_probe(self.port, "GET", "/health")
            if probe.body and probe.body.get("worker_pid"):
                self.worker_pid = probe.body["worker_pid"]
                self.pids.append(self.worker_pid)
            else:
                time.sleep(POLL_SECONDS)

    def stop(self, grace_s: float = 3.0) -> Stopped:
        """SIGTERM the app, give it ``grace_s`` seconds, then kill the whole group. Always ends with the leader reaped."""
        started = time.perf_counter()
        if self.process is None or self.process.poll() is not None:
            code = self.process.returncode if self.process else None
            return Stopped("already_exited", code, 0.0)
        self.process.terminate()
        try:
            code = self.process.wait(grace_s)
        except subprocess.TimeoutExpired:
            self._kill_group()
            code = self.process.wait(grace_s)
            return Stopped("killed", code, round((time.perf_counter() - started) * 1000, 1))
        method = "graceful" if code == 0 else "terminated"
        return Stopped(method, code, round((time.perf_counter() - started) * 1000, 1))

    def kill_leader(self) -> Stopped:
        """SIGKILL only the app process, the way a crash or an impatient `kill` would. Its worker is not touched."""
        started = time.perf_counter()
        os.kill(self.process.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        code = self.process.wait(3)
        return Stopped("killed", code, round((time.perf_counter() - started) * 1000, 1))

    def crash_group(self) -> Stopped:
        """Kill the app and everything in its group at once: a power cut as far as the app can tell."""
        started = time.perf_counter()
        self._kill_group()
        code = self.process.wait(3)
        return Stopped("killed", code, round((time.perf_counter() - started) * 1000, 1))

    def _kill_group(self) -> None:
        if not any(pid_alive(pid) for pid in self.pids):
            return  # nothing of this run is left, and a group id may already belong to someone else
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True, check=False)
            return
        try:
            os.killpg(self.process.pid, signal.SIGKILL)  # the group id equals the leader's pid (own session)
        except ProcessLookupError:
            pass  # no member left

    def reap(self) -> None:
        """Last resort for the context manager: nothing from this run may outlive it."""
        if self.process is not None:
            self._kill_group()
            try:
                self.process.wait(3)
            except subprocess.TimeoutExpired:
                pass

    def log_text(self) -> str:
        return self.log_path.read_text(encoding="utf-8", errors="replace") if self.log_path.exists() else ""


def credential_env(secret: str, **extra: str) -> dict[str, str]:
    """The NOTES_* environment of a normal start: a model name, the credential and any overrides."""
    return {ENV_PREFIX + "MODEL": "demo-model", ENV_PREFIX + "API_KEY": secret, **extra}
