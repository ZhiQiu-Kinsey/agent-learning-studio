"""notes_app: the small local service that the delivery checks start, probe, stop and inspect.

It is deliberately a real server, not a stub: layered settings, a data file, a /health and a /ready
endpoint, JSON logs on stderr, a background worker process and a clean stop on SIGTERM. Run it as
``python -m lessons.lesson_local_delivery.notes_app --workdir <dir>``. The ``--fault`` flag injects one
defect at a time so the checks have something real to catch; it is test equipment, not a feature.
"""
import argparse
import errno
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from lessons.lesson_local_delivery.notes_store import InvalidNote, LimitReached, NotesStore, StoreCorrupt
from lessons.lesson_local_delivery.settings import (ENV_PREFIX, LEVELS, SECRET_LIKE, SETTINGS, VERSION,
                                                    SettingsError, load_settings)

EXIT_CONFIG, EXIT_BIND, EXIT_DATA = 2, 3, 5
FAULTS = ("none", "hang-before-listen", "stuck-warmup", "leak-config-log")
# The worker stands for a background helper (an indexer, a queue consumer). It is a separate process
# on purpose: stopping the app must also stop it, and only a test can tell whether it did.
WORKER_CODE = "import time\nwhile True:\n    time.sleep(1)\n"
MAX_BODY = 4096


class Logger:
    """One JSON object per line on stderr: ts, level, event, then the event's own fields."""

    def __init__(self):
        self.threshold = LEVELS.index("info")
        self.lock = threading.Lock()

    def emit(self, level: str, event: str, **fields) -> None:
        if LEVELS.index(level) < self.threshold:
            return
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "level": level,
                  "event": event, **fields}
        with self.lock:
            sys.stderr.write(json.dumps(record) + "\n")
            sys.stderr.flush()


class Server(ThreadingHTTPServer):
    # http.server turns address reuse on by default. Off here: a second copy on a busy port must fail loudly
    # instead of sharing the port (Windows would let it), and the failure is what the checks look for.
    allow_reuse_address = False
    daemon_threads = True


class App:
    def __init__(self, resolved, store, log, warmup_ms, fault):
        self.resolved, self.store, self.log = resolved, store, log
        self.warmup_ms, self.fault = warmup_ms, fault
        self.started = time.monotonic()
        self.listen_ms = None
        self.ready = threading.Event()
        self.worker = None
        self.server = None

    def uptime_ms(self) -> int:
        return round((time.monotonic() - self.started) * 1000)


class Handler(BaseHTTPRequestHandler):
    app: App
    timeout = 5  # a client that stalls must not hold a thread forever

    def log_message(self, *args):  # the default writes to stderr in a free format; ours is JSON, below
        pass

    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.app.log.emit("debug", "request", method=self.command, path=self.path.split("?")[0], status=status)

    def do_GET(self):
        app = self.app
        path = self.path.split("?")[0]
        if path == "/health":
            # Liveness: the process is up and answering. It says nothing about whether it can do its job.
            self._send(200, {"status": "ok", "version": VERSION, "pid": os.getpid(),
                             "worker_pid": app.worker.pid if app.worker else None, "uptime_ms": app.uptime_ms()})
        elif path == "/ready":
            ready = app.ready.is_set()
            self._send(200 if ready else 503, {"ready": ready, "startup_ms": app.listen_ms,
                                               "checks": {"config": True, "data_store": True, "warmup": ready}})
        elif path == "/config":
            names = sorted(name for name in os.environ if SECRET_LIKE.search(name))
            self._send(200, {"settings": app.resolved.public(), "bind": app.server.server_address[0],
                             "secret_like_env": names})
        elif path == "/notes":
            if not app.ready.is_set():
                return self._send(503, {"error": "not_ready"})
            notes = app.store.snapshot()
            self._send(200, {"count": len(notes), "notes": notes})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):
        app = self.app
        if self.path.split("?")[0] != "/notes":
            return self._send(404, {"error": "not_found"})
        if not app.ready.is_set():
            return self._send(503, {"error": "not_ready"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"error": "invalid_json"})
        try:
            note, duplicate = app.store.add(body.get("op_id"), body.get("text"))
        except InvalidNote as error:
            return self._send(400, {"error": "invalid_note", "field": str(error)})
        except LimitReached:
            return self._send(409, {"error": "limit_reached"})
        self._send(200 if duplicate else 201, {"note": note, "duplicate": duplicate})


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="notes_app: a small local service for the delivery checks")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--config", help="settings file name inside the working directory")
    parser.add_argument("--port-file", help="written with the port number once the socket is listening")
    parser.add_argument("--warmup-ms", type=int, default=400)
    parser.add_argument("--fault", choices=FAULTS, default="none")
    return parser.parse_args(argv)


def _write_port(path: Path, port: int) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(str(port), encoding="ascii")
    os.replace(temp, path)  # the reader sees the whole number or no file, never half of it


def _warm_up(app: App) -> None:
    app.log.emit("info", "warming_up", warmup_ms=app.warmup_ms)
    time.sleep(app.warmup_ms / 1000)
    if app.fault == "stuck-warmup":
        threading.Event().wait()  # a dependency that never answers: the process lives, readiness never comes
    app.ready.set()
    app.log.emit("info", "ready", ready_ms=app.uptime_ms())


def main(argv=None) -> int:
    args = parse_args(argv)
    log = Logger()
    log.emit("info", "start", pid=os.getpid(), version=VERSION, fault=args.fault)
    # Handlers go in before anything slow: a SIGTERM that arrives early is remembered and acted on once the app
    # is up, instead of killing it half-way (the default action) and skipping the clean stop.
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    workdir = Path(args.workdir)
    # 1. Settings first, before anything is opened or bound: a bad configuration must fail here, with names.
    try:
        resolved = load_settings(workdir / args.config if args.config else None, os.environ)
    except SettingsError as error:
        log.emit("error", "config_invalid", problems=[problem.as_dict() for problem in error.problems])
        return EXIT_CONFIG
    log.threshold = LEVELS.index(resolved.values["log_level"])
    for warning in resolved.warnings:
        log.emit("warning", "unknown_env", name=warning.name)
    # Names and sources only; for a credential, just whether it is set.
    log.emit("info", "config_loaded", sources=resolved.sources, settings_file=bool(args.config),
             credentials={setting.name: {"set": True, "source": resolved.sources[setting.name]}
                          for setting in SETTINGS if setting.secret})
    if args.fault == "leak-config-log":
        # The defect: "log the config to help debugging" writes the whole dictionary, credential included.
        log.emit("info", "config_dump", config=resolved.values)
    if args.fault == "hang-before-listen":
        while True:
            time.sleep(0.2)  # alive, never binds, ignores SIGTERM, never says why
    # 2. The data file, then the socket.
    try:
        store = NotesStore(workdir / resolved.values["data_dir"] / "notes.json", resolved.values["max_notes"])
    except StoreCorrupt:
        log.emit("error", "data_corrupt")
        return EXIT_DATA
    app = App(resolved, store, log, args.warmup_ms, args.fault)
    Handler.app = app
    try:
        app.server = Server((resolved.values["host"], resolved.values["port"]), Handler)
    except OSError as error:
        # Never fall back to another port: the operator asked for this one, and a silent move breaks every client.
        log.emit("error", "bind_failed", reason=errno.errorcode.get(error.errno, "OSError"),
                 port=resolved.values["port"])
        return EXIT_BIND
    host, port = app.server.server_address[:2]
    if args.port_file:
        _write_port(Path(args.port_file), port)
    app.listen_ms = app.uptime_ms()
    log.emit("info", "listening", host=host, port=port, startup_ms=app.listen_ms, version=VERSION)
    # 3. The worker and the warm-up; then serve until SIGTERM.
    child_env = {name: value for name, value in os.environ.items() if not name.startswith(ENV_PREFIX)}
    app.worker = subprocess.Popen([sys.executable, "-c", WORKER_CODE], env=child_env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log.emit("info", "worker_started", worker_pid=app.worker.pid)
    threading.Thread(target=_warm_up, args=(app,), daemon=True).start()
    # serve_forever polls for shutdown; the default 0.5 s would make every stop wait that long.
    threading.Thread(target=app.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    while not stop.wait(0.2):
        pass
    # 4. A clean stop: refuse new connections, stop the worker, say so in the log.
    log.emit("info", "shutdown_requested")
    app.server.shutdown()
    app.server.server_close()
    app.worker.terminate()
    try:
        app.worker.wait(3)
    except subprocess.TimeoutExpired:
        app.worker.kill()
        app.worker.wait()
    log.emit("info", "stopped", exit_code=0, uptime_ms=app.uptime_ms())
    return 0


if __name__ == "__main__":
    sys.exit(main())
