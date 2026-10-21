"""local-delivery: start, probe, stop and inspect a small real local service. This lesson calls no model.

The service is notes_app.py, started as a child process on a random loopback port in a throwaway directory.
Every check talks to that real process: configuration is resolved by the app itself, a refusal is the app's
real exit code, a timeout is a clock that really ran out, "no orphans" is a pid that really disappeared.
The only credential in a run is a fake key made up for this run; it is handed to the app and then searched for
in every log line, report and event, and none of them may contain it.
"""
import hashlib
import json
import shutil
import socket
import tempfile
from pathlib import Path
from secrets import token_hex
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_local_delivery import logscan
from lessons.lesson_local_delivery.launcher import (AppProcess, Listening, Stopped, Waited, credential_env, http_probe,
                                                other_interface_address, port_accepts, wait_gone)
from lessons.lesson_local_delivery.locales import Texts, texts_for
from lessons.lesson_local_delivery.settings import SETTINGS, SOURCES, VERSION, Setting, load_settings, read_file


class Inputs(LessonInputs):
    scenario: Literal["config_layers", "startup_probe", "logs_secrets", "restart_rollback"] = "config_layers"
    # How long the runner waits for the app to listen, and then for /ready to answer 200. Both end in a report, not a hang.
    startup_timeout_ms: int = Field(default=1200, ge=300, le=5000)
    ready_timeout_ms: int = Field(default=1200, ge=300, le=5000)
    # The app's simulated dependency warm-up: /health is up at once, /ready only after this long.
    warmup_ms: int = Field(default=400, ge=100, le=1500)


INPUT_MODEL = Inputs


def new_demo_secret() -> str:
    """A fake credential made up for this run. The lesson never reads a real key."""
    return "sk-demo-" + token_hex(12)


class SecretLeak(RuntimeError):
    """A payload about to be published held a credential value: a bug in this lesson, not in the app."""


class Evidence:
    """Publishes events and reports, and refuses to publish anything that contains a credential value."""

    def __init__(self, context: RunContext, secrets: dict[str, str]):
        self.context, self.secrets = context, secrets

    def emit(self, kind: str, data: dict, round_number: int) -> None:
        if logscan.scan_text(json.dumps(data, ensure_ascii=False), self.secrets):
            raise SecretLeak(kind)
        self.context.emit(kind, data, round_number)

    def process(self, round_number: int, scenario: str, app: AppProcess, phase: str, **fields) -> None:
        self.emit("lesson.process", {"scenario": scenario, "app": app.name, "pid": app.pid, "phase": phase, **fields},
                  round_number)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def ms(value: float) -> str:
    return f"{value:.0f} ms"


class Delivery:
    """What every scenario shares: the working directory, the fake credential, the texts and the evidence."""

    def __init__(self, context: RunContext, workdir: Path, secret: str, values: dict):
        self.context, self.workdir, self.values, self.secret = context, workdir, values, secret
        self.t: Texts = texts_for(context.locale)
        self.secrets = {"api_key": secret}
        self.ev = Evidence(context, self.secrets)
        self.check = context.check_cancelled

    # ----- small builders -----
    def app(self, name: str, env: dict[str, str], *, config: str | None = None, fault: str = "none") -> AppProcess:
        return AppProcess(self.workdir, env, config=config, warmup_ms=self.values["warmup_ms"], fault=fault, name=name)

    def credentials(self, **extra: str) -> dict[str, str]:
        return credential_env(self.secret, **extra)

    def write_settings(self, content: dict) -> Path:
        path = self.workdir / "settings.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        return path

    def item(self, name: str, passed: bool, **detail) -> dict:
        return {"id": name, "label": self.t.check_labels[name], "passed": bool(passed),
                "detail": self.t.check_details[name].format(**detail)}

    def metric(self, name: str, value) -> dict:
        # A value the run could not obtain is shown as a dash, never as a made-up number.
        return {"id": name, "label": self.t.metric_labels[name], "value": "—" if value is None else value}

    def report(self, key: str, round_number: int, checks: list, metrics: list, rows: list | None = None) -> tuple[int, int]:
        data = {"title": self.t.titles[key], "summary": self.t.summaries[key], "checks": checks, "metrics": metrics}
        if rows is not None:
            data["table"] = {"columns": list(self.t.columns[key]), "rows": rows}
        self.ev.emit("lesson.report", data, round_number)
        return sum(item["passed"] for item in checks), len(checks)

    # ----- the steps of a start -----
    def spawn(self, app: AppProcess, scenario: str, rnd: int) -> None:
        self.check()
        app.start()
        self.ev.process(rnd, scenario, app, "spawned")

    def listen(self, app: AppProcess, scenario: str, rnd: int) -> Listening:
        result = app.wait_listening(self.values["startup_timeout_ms"] / 1000, self.check)
        if result.state == "listening":
            self.ev.process(rnd, scenario, app, "listening", port=result.port, listen_ms=result.elapsed_ms)
        else:
            self._failed(app, scenario, rnd, result)
        return result

    def _failed(self, app: AppProcess, scenario: str, rnd: int, result: Listening) -> None:
        lines = self.lines(app)
        invalid = logscan.find(lines, "config_invalid")
        bind = logscan.find(lines, "bind_failed")
        if result.state == "timeout":
            reason = "startup_timeout"
        elif invalid is not None:
            reason = "config_invalid"
        elif bind is not None:
            reason = "port_in_use" if "ADDRINUSE" in str(bind.get("reason")) else "bind_failed"
        else:
            reason = "exited"
        names = logscan.events(lines)
        data = {"scenario": scenario, "app": app.name, "reason": reason, "exit_code": result.exit_code,
                "elapsed_ms": result.elapsed_ms, "last_log_event": names[-1] if names else None,
                "alive": app.process.poll() is None}
        if invalid is not None:
            data["problems"] = invalid.get("problems", [])
        self.ev.emit("lesson.start_failed", data, rnd)

    def wait_ready(self, app: AppProcess, scenario: str, rnd: int) -> Waited:
        waited = app.wait_ready(self.values["ready_timeout_ms"] / 1000, self.check)
        for probe in waited.probes:
            self.ev.emit("lesson.probe", {"scenario": scenario, "app": app.name, "request": probe.endpoint,
                                          "status": probe.status, "at_ms": probe.at_ms,
                                          "latency_ms": probe.elapsed_ms}, rnd)
        if waited.state == "ready":
            self.ev.process(rnd, scenario, app, "ready", ready_ms=waited.elapsed_ms)
        elif waited.state == "not_ready":
            self.ev.process(rnd, scenario, app, "not_ready", limit_ms=self.values["ready_timeout_ms"],
                            waited_ms=waited.elapsed_ms)
        return waited

    def start_ready(self, app: AppProcess, scenario: str, rnd: int) -> tuple[Listening, Waited]:
        self.spawn(app, scenario, rnd)
        listening = self.listen(app, scenario, rnd)
        if listening.state != "listening":
            return listening, Waited("exited", listening.elapsed_ms)
        return listening, self.wait_ready(app, scenario, rnd)

    def stop(self, app: AppProcess, scenario: str, rnd: int, grace_s: float = 3.0) -> tuple[Stopped, list[int]]:
        stopped = app.stop(grace_s)
        left = wait_gone(app.pids)
        self.ev.process(rnd, scenario, app, "stopped", stop_method=stopped.method, exit_code=stopped.exit_code,
                        took_ms=stopped.elapsed_ms, pids_left=len(left))
        return stopped, left

    def lines(self, app: AppProcess) -> list[logscan.LogLine]:
        return logscan.parse(app.log_text())

    def answer(self, key: str, passed: int, total: int, **extra) -> str:
        return self.t.answers[key].format(passed=passed, total=total, **extra)


class Tally:
    """Counts passed and total checks over several reports."""

    def __init__(self):
        self.passed = self.total = 0

    def add(self, result: tuple[int, int]) -> None:
        self.passed += result[0]
        self.total += result[1]


def problems_of(lines: list[logscan.LogLine]) -> list[dict]:
    return (logscan.find(lines, "config_invalid") or {}).get("problems", [])


# ---------------------------------------------------------------- scenario 1: configuration layers

def _shown(t: Texts, setting: Setting, value) -> str:
    """A credential is only ever shown as "set"; every other value is shown as it is."""
    return t.values["set"] if setting.secret else str(value)


def config_layers(d: Delivery) -> str:
    t, tally = d.t, Tally()
    # 1. Three layers, resolved twice: predicted here with the app's own settings module, then by a real child.
    config_path = d.write_settings({"settings_version": 1, "model": "file-model", "log_level": "warning",
                                    "max_notes": 50})
    env = d.credentials(NOTES_MODEL="env-model", NOTES_MODLE="typo")
    predicted = load_settings(config_path, env)
    file_values, _ = read_file(config_path)
    with d.app("layers", env, config="settings.json") as app:
        d.spawn(app, "config_layers", 1)
        listening = d.listen(app, "config_layers", 1)
        probe = None
        if listening.state == "listening":
            app.note_worker()
            probe = http_probe(app.port, "GET", "/config")
        stopped, left = d.stop(app, "config_layers", 1)
        lines = d.lines(app)
    body = (probe.body if probe else None) or {}
    child = {row["name"]: row for row in body.get("settings", [])}
    visible = body.get("secret_like_env", [])
    rows = []
    for setting in SETTINGS:
        raw = env.get(setting.env)
        rows.append([setting.name, "—" if setting.default is None else str(setting.default),
                     "—" if setting.name not in file_values else str(file_values[setting.name]),
                     "—" if raw is None else _shown(t, setting, raw), child.get(setting.name, {}).get("source", "—"),
                     _shown(t, setting, child.get(setting.name, {}).get("value", "—"))])
    counts = {source: sum(1 for value in predicted.sources.values() if value == source) for source in SOURCES}
    unknown = [warning.name for warning in predicted.warnings]
    warned = logscan.find(lines, "unknown_env") or {}
    api = child.get("api_key", {})
    model = child.get("model", {})
    checks = [
        d.item("env-beats-file", model.get("source") == "env" and model.get("value") == "env-model"
               and predicted.sources["model"] == "env"),
        d.item("file-beats-default", all(child.get(name, {}).get("source") == "file" for name in ("log_level", "max_notes"))),
        d.item("default-fills", all(child.get(name, {}).get("source") == "default" for name in ("host", "port", "data_dir"))),
        d.item("credential-env-only", api.get("source") == "env" and api.get("set") is True and "value" not in api
               and probe is not None and not logscan.scan_text(probe.text, d.secrets)),
        d.item("settings-file-clean", not logscan.scan_text(config_path.read_text("utf-8"), d.secrets),
               file="settings.json"),
        d.item("typo-warned", warned.get("name") == "NOTES_MODLE", names=t.values["separator"].join(unknown) or "—"),
        d.item("child-matches", bool(child) and all(child[name]["source"] == predicted.sources[name]
                                                   for name in predicted.sources)),
        d.item("env-isolated", visible == ["NOTES_API_KEY"], names=", ".join(visible) or "—"),
    ]
    metrics = [d.metric("sources-env", counts["env"]), d.metric("sources-file", counts["file"]),
               d.metric("sources-default", counts["default"]), d.metric("pids-left", len(left)),
               d.metric("model-calls", 0)]
    tally.add(d.report("layers", 1, checks, metrics, rows))

    # 2. Nothing configured, and one value that is not a port: the app must refuse before it binds anything.
    with d.app("missing", {"NOTES_PORT": "not-a-port"}) as app:
        d.spawn(app, "config_layers", 2)
        result = d.listen(app, "config_layers", 2)
        lines = d.lines(app)
        left = wait_gone(app.pids)
    problems = problems_of(lines)
    codes = {(item["name"], item["code"]) for item in problems}
    checks = [
        d.item("missing-refused", result.state == "exited" and result.exit_code == 2 and app.port is None and not left,
               code=result.exit_code),
        d.item("missing-all-named", {("model", "missing"), ("api_key", "missing"), ("port", "invalid")} <= codes,
               count=len(problems)),
        d.item("missing-no-value", "not-a-port" not in app.log_text()),
    ]
    rows = [[item["name"], t.codes[item["code"]], item["code"]] for item in problems]
    tally.add(d.report("missing", 2, checks, [d.metric("exit-code", result.exit_code),
                                              d.metric("time-to-exit", ms(result.elapsed_ms)),
                                              d.metric("problems", len(problems))], rows))

    # 3. The settings file carries the credential and a mistyped key. Both must be refused even though the
    #    environment holds a valid credential, and the refusal must not copy the value into the log.
    config_path = d.write_settings({"settings_version": 1, "model": "file-model", "api_key": d.secret,
                                    "log_lvl": "debug"})
    with d.app("file-secret", d.credentials(), config="settings.json") as app:
        d.spawn(app, "config_layers", 3)
        result = d.listen(app, "config_layers", 3)
        lines = d.lines(app)
        left = wait_gone(app.pids)
    problems = problems_of(lines)
    codes = {(item["name"], item["code"]) for item in problems}
    in_file = logscan.scan_text(config_path.read_text("utf-8"), d.secrets)
    checks = [
        d.item("file-secret-refused", ("api_key", "secret_in_file") in codes and result.state == "exited" and not left,
               code=result.exit_code),
        d.item("file-typo-refused", ("log_lvl", "unknown_key") in codes),
        d.item("file-refusal-clean", not logscan.leaks(lines, d.secrets)),
        d.item("file-secret-scan", bool(in_file), file="settings.json", setting=", ".join(in_file) or "—"),
    ]
    rows = [[item["name"], t.codes[item["code"]], item["code"]] for item in problems]
    tally.add(d.report("file-secret", 3, checks, [d.metric("exit-code", result.exit_code),
                                                  d.metric("problems", len(problems))], rows))
    return d.answer("config_layers", tally.passed, tally.total, model=predicted.values["model"])


# ---------------------------------------------------------------- scenario 2: start, probe, stop

def _probe_rows(waited: Waited) -> list[list]:
    return [[round(probe.at_ms), probe.endpoint, probe.status if probe.status is not None else "—",
             round(probe.elapsed_ms, 1)] for probe in waited.probes]


def startup_probe(d: Delivery) -> str:
    t, tally = d.t, Tally()
    limit_ms = d.values["startup_timeout_ms"]
    # 1. A normal start: listening, liveness at once, readiness after the warm-up, a stop, nothing left behind.
    with d.app("normal", d.credentials()) as app:
        listening, waited = d.start_ready(app, "startup_probe", 1)
        config = health = reached = None
        outside = other_interface_address()
        if listening.state == "listening":
            config = http_probe(app.port, "GET", "/config")
            health = http_probe(app.port, "GET", "/health")
            reached = http_probe(app.port, "GET", "/health", host=outside) if outside else None
        port = app.port
        graceful, graceful_left = d.stop(app, "startup_probe", 1)
        graceful_pids = len(app.pids)
        lines = d.lines(app)
    ready_probes = [probe for probe in waited.probes if probe.endpoint == "GET /ready"]
    bind = ((config.body if config else None) or {}).get("bind")
    reported = logscan.find(lines, "listening") or {}
    checks = [
        d.item("health-before-ready", bool(ready_probes) and ready_probes[0].status == 503
               and any(p.endpoint == "GET /health" and p.status == 200 for p in waited.probes),
               warmup=d.values["warmup_ms"]),
        d.item("ready-reached", waited.state == "ready", limit=d.values["ready_timeout_ms"], waited=ms(waited.elapsed_ms)),
        d.item("loopback-only", bind == "127.0.0.1" and (reached is None or reached.status is None), bind=bind or "—",
               tested=t.values["tested"] if outside else t.values["not_tested"]),
        d.item("stopped-gracefully", graceful.method == "graceful", method=t.stop_methods[graceful.method],
               code=graceful.exit_code),
        d.item("no-orphans", not graceful_left and logscan.find(lines, "stopped") is not None, pids=graceful_pids),
        d.item("port-released", port is not None and not port_accepts(port), port=port),
    ]
    metrics = [d.metric("listen-ms", ms(listening.elapsed_ms)), d.metric("startup-ms", reported.get("startup_ms")),
               d.metric("ready-ms", ms(waited.elapsed_ms)), d.metric("stop-ms", ms(graceful.elapsed_ms)),
               d.metric("version", ((health.body if health else None) or {}).get("version", "—"))]
    tally.add(d.report("normal", 1, checks, metrics, _probe_rows(waited)))

    # 2. A start that never finishes: the process lives, never listens, ignores SIGTERM. The runner must say so.
    with d.app("hang", d.credentials(), fault="hang-before-listen") as app:
        d.spawn(app, "startup_probe", 2)
        result = d.listen(app, "startup_probe", 2)
        alive = app.process.poll() is None
        stopped, left = d.stop(app, "startup_probe", 2, grace_s=0.5)
        names = logscan.events(d.lines(app))
    checks = [
        d.item("hang-timeout-reported", result.state == "timeout", limit=limit_ms),
        d.item("hang-alive", alive, pid=app.pid),
        d.item("hang-no-port", app.port is None and not app.port_file.exists()),
        d.item("hang-reaped", not left, method=t.stop_methods[stopped.method]),
    ]
    metrics = [d.metric("limit-ms", limit_ms), d.metric("last-log-event", names[-1] if names else "—"),
               d.metric("stop-method", t.stop_methods[stopped.method])]
    tally.add(d.report("hang", 2, checks, metrics, [[number, name] for number, name in enumerate(names, 1)]))

    # 3. Alive but never ready: /health says 200, /ready keeps saying 503, and the wait ends at the limit.
    with d.app("unready", d.credentials(), fault="stuck-warmup") as app:
        listening, waited = d.start_ready(app, "startup_probe", 3)
        last = http_probe(app.port, "GET", "/ready") if listening.state == "listening" else None
        stopped, left = d.stop(app, "startup_probe", 3)
    failing = sorted(name for name, ok in (((last.body if last else None) or {}).get("checks") or {}).items() if not ok)
    checks = [
        d.item("unready-health-ok", any(p.endpoint == "GET /health" and p.status == 200 for p in waited.probes)),
        d.item("unready-not-ready", waited.state == "not_ready" and last is not None and last.status == 503,
               limit=d.values["ready_timeout_ms"], failing=", ".join(failing) or "—"),
        d.item("unready-reaped", not left and stopped.method == "graceful", method=t.stop_methods[stopped.method]),
    ]
    metrics = [d.metric("limit-ms", d.values["ready_timeout_ms"]),
               d.metric("ready-status", last.status if last else "—"), d.metric("failing-check", ", ".join(failing) or "—")]
    tally.add(d.report("unready", 3, checks, metrics, _probe_rows(waited)))

    # 4. The port is taken: the app must refuse with a reason and must not move to another port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.bind(("127.0.0.1", 0))
        occupier.listen(1)
        busy = occupier.getsockname()[1]
        with d.app("busy", d.credentials(NOTES_PORT=str(busy))) as app:
            d.spawn(app, "startup_probe", 4)
            result = d.listen(app, "startup_probe", 4)
            lines = d.lines(app)
            left = wait_gone(app.pids)
        still = port_accepts(busy)
    failure = logscan.find(lines, "bind_failed") or {}
    checks = [
        d.item("busy-refused", result.state == "exited" and result.exit_code == 3
               and "ADDRINUSE" in str(failure.get("reason")), code=result.exit_code, reason=failure.get("reason", "—")),
        d.item("busy-no-fallback", logscan.find(lines, "listening") is None and app.port is None and not left),
        d.item("busy-occupier-intact", still, port=busy),
    ]
    rows = [[number, line.record.get("level"), line.record.get("event")]
            for number, line in enumerate(lines, 1) if line.record]
    tally.add(d.report("busy", 4, checks, [d.metric("exit-code", result.exit_code),
                                           d.metric("time-to-exit", ms(result.elapsed_ms)),
                                           d.metric("bind-reason", failure.get("reason", "—"))], rows))

    # 5. Two ways to stop: kill only the app (its worker survives as an orphan), then kill the whole group.
    with d.app("orphan", d.credentials()) as app:
        d.spawn(app, "startup_probe", 5)
        listening = d.listen(app, "startup_probe", 5)
        if listening.state == "listening":
            app.note_worker()
        started_pids = len(app.pids)
        crashed = app.kill_leader()
        survivors = wait_gone(app.pids, 0.3)
        d.ev.process(5, "startup_probe", app, "leader_killed", exit_code=crashed.exit_code, orphans=len(survivors))
        app.crash_group()
        left = wait_gone(app.pids)
        d.ev.process(5, "startup_probe", app, "group_reaped", pids_left=len(left))
    rows = [[t.stop_modes["graceful"], t.stop_methods[graceful.method], graceful_pids, len(graceful_left)],
            [t.stop_modes["leader"], t.stop_methods[crashed.method], started_pids, len(survivors)],
            [t.stop_modes["group"], t.stop_methods["killed"], started_pids, len(left)]]
    checks = [d.item("group-reaped", not left and listening.state == "listening", pids=started_pids)]
    tally.add(d.report("orphan", 5, checks, [d.metric("orphans-after-leader-kill", len(survivors)),
                                             d.metric("orphans-after-group-kill", len(left))], rows))
    return d.answer("startup_probe", tally.passed, tally.total, orphans=len(survivors))


# ---------------------------------------------------------------- scenario 3: logs and credentials

LOG_TABLE_ROWS = 12


def _log_rows(d: Delivery, lines: list[logscan.LogLine]) -> list[list]:
    rows = []
    for line in lines:
        if line.record is None or line.record.get("event") == "request":
            continue
        fields = {key: value for key, value in line.record.items() if key not in ("ts", "level", "event")}
        rows.append([line.number, line.record.get("level"), line.record.get("event"),
                     logscan.redact(json.dumps(fields, separators=(",", ":")), d.secrets)])
    return rows[:LOG_TABLE_ROWS]


def logs_secrets(d: Delivery) -> str:
    t, tally = d.t, Tally()
    # 1. A normal run at debug level, with a write and a read, then a clean stop; then read the log back.
    with d.app("normal", d.credentials(NOTES_LOG_LEVEL="debug")) as app:
        listening, waited = d.start_ready(app, "logs_secrets", 1)
        if waited.state == "ready":
            http_probe(app.port, "POST", "/notes", {"op_id": "note-1", "text": t.values["sample_note"]})
            http_probe(app.port, "GET", "/notes")
        d.stop(app, "logs_secrets", 1)
        lines = d.lines(app)
    loaded = logscan.find(lines, "config_loaded") or {}
    reported = logscan.find(lines, "listening") or {}
    requests = [line for line in lines if line.record and line.record.get("event") == "request"]
    checks = [
        d.item("log-structured", logscan.structured(lines), count=len(lines)),
        d.item("log-lifecycle", logscan.lifecycle_in_order(lines), events=" → ".join(logscan.LIFECYCLE)),
        d.item("log-sources", set(loaded.get("sources", {})) == {setting.name for setting in SETTINGS}
               and loaded.get("credentials") == {"api_key": {"set": True, "source": "env"}}),
        d.item("log-clean", not logscan.leaks(lines, d.secrets)),
        d.item("log-startup-measured", isinstance(reported.get("startup_ms"), int) and reported.get("version") == VERSION,
               ms=reported.get("startup_ms"), version=reported.get("version")),
    ]
    metrics = [d.metric("log-lines", len(lines)), d.metric("startup-ms", reported.get("startup_ms")),
               d.metric("version", reported.get("version", "—")), d.metric("request-lines", len(requests))]
    tally.add(d.report("log-normal", 1, checks, metrics, _log_rows(d, lines)))

    # 2. The same app with one defect: it dumps its whole configuration into the log. The scan must catch it,
    #    and nothing shown here may carry the value.
    with d.app("leaky", d.credentials(), fault="leak-config-log") as app:
        d.start_ready(app, "logs_secrets", 2)
        d.stop(app, "logs_secrets", 2)
        lines = d.lines(app)
    found = logscan.leaks(lines, d.secrets)
    by_number = {line.number: line for line in lines}
    shown = [logscan.redact(by_number[hit.line].text, d.secrets) for hit in found]
    first = found[0] if found else None
    checks = [
        d.item("leak-log-clean", not found, count=len(found)),
        d.item("leak-located", first is not None, line=first.line if first else "—",
               event=first.event if first else "—", setting=first.setting if first else "—"),
        d.item("leak-report-clean", not logscan.scan_text("\n".join(shown), d.secrets)),
    ]
    metrics = [d.metric("release-gate", t.values["blocked"] if found else t.values["released"]),
               d.metric("leaked-settings", ", ".join(sorted({hit.setting for hit in found})) or "—"),
               d.metric("log-lines", len(lines))]
    rows = [[hit.line, hit.event, hit.setting, text] for hit, text in zip(found, shown)]
    tally.add(d.report("log-leak", 2, checks, metrics, rows))
    return d.answer("logs_secrets", tally.passed, tally.total, leaks=len(found))


# ---------------------------------------------------------------- scenario 4: restart and rollback

def _notes(app: AppProcess):
    probe = http_probe(app.port, "GET", "/notes")
    body = probe.body or {}
    return probe, body.get("count"), [note["op_id"] for note in body.get("notes", [])]


def restart_rollback(d: Delivery) -> str:
    t, tally = d.t, Tally()
    settings_path = d.write_settings({"settings_version": 1, "model": "file-model", "max_notes": 100})
    notes_path = d.workdir / "data" / "notes.json"
    env = {"NOTES_API_KEY": d.secret}
    # 1. A first run writes two notes; the settings and the data are backed up; then the whole process group is killed.
    with d.app("run1", env, config="settings.json") as app:
        listening, waited = d.start_ready(app, "restart_rollback", 1)
        writes = []
        if waited.state == "ready":
            writes = [http_probe(app.port, "POST", "/notes", {"op_id": f"op-{n}", "text": t.values["sample_note"]})
                      for n in (1, 2)]
        backup = d.workdir / "backup"
        backup.mkdir()
        shutil.copy2(settings_path, backup / "settings.json")
        shutil.copy2(notes_path, backup / "notes.json")
        saved = {"settings": digest(settings_path), "notes": digest(notes_path)}
        before_crash, old_port = digest(notes_path), app.port
        crashed = app.crash_group()
        d.ev.process(1, "restart_rollback", app, "crashed", exit_code=crashed.exit_code)
        crash_left = wait_gone(app.pids)
    intact = digest(notes_path) == before_crash and bool(json.loads(notes_path.read_text("utf-8"))["notes"])

    # 2. A new process on the same files: the notes are back; the client retries op-2 and nothing is written twice.
    with d.app("run2", env, config="settings.json") as app:
        listening, waited = d.start_ready(app, "restart_rollback", 2)
        restored = repeat = fresh = None
        after_repeat = final = (None, None, [])
        if waited.state == "ready":
            restored = _notes(app)
            repeat = http_probe(app.port, "POST", "/notes", {"op_id": "op-2", "text": t.values["sample_note"]})
            after_repeat = _notes(app)
            fresh = http_probe(app.port, "POST", "/notes", {"op_id": "op-3", "text": t.values["sample_note"]})
            final = _notes(app)
        d.stop(app, "restart_rollback", 2)
    duplicate = bool(repeat and repeat.body and repeat.body.get("duplicate") is True)
    checks = [
        d.item("crash-reaped", not crash_left and old_port is not None and not port_accepts(old_port),
               pids=len(app.pids)),
        d.item("crash-data-intact", intact),
        d.item("restart-restored", restored is not None and restored[1] == 2 and restored[2] == ["op-1", "op-2"]),
        d.item("restart-no-duplicate", duplicate and repeat.status == 200 and after_repeat[1] == 2),
        d.item("restart-new-write", fresh is not None and fresh.status == 201 and final[1] == 3),
    ]
    rows = [[1, "POST /notes op-1", writes[0].status if writes else "—", "—"],
            [1, "POST /notes op-2", writes[1].status if writes else "—", "—"],
            [2, "GET /notes", restored[0].status if restored else "—", restored[1] if restored else "—"],
            [2, "POST /notes op-2", repeat.status if repeat else "—", after_repeat[1] if after_repeat[0] else "—"],
            [2, "POST /notes op-3", fresh.status if fresh else "—", final[1] if final[0] else "—"]]
    metrics = [d.metric("notes-before-crash", len(writes)),
               d.metric("notes-after-restart", restored[1] if restored else "—"),
               d.metric("duplicate-writes", (after_repeat[1] - 2) if after_repeat[1] is not None else "—")]
    tally.add(d.report("restart", 2, checks, metrics, rows))

    # 3. An upgraded settings file that this version cannot read: the app must refuse, and the data must not move.
    before_upgrade = digest(notes_path)
    d.write_settings({"settings_version": 2, "model_id": "file-model", "max_notes": 100})
    with d.app("upgrade", env, config="settings.json") as app:
        d.spawn(app, "restart_rollback", 3)
        refused = d.listen(app, "restart_rollback", 3)
        upgrade_lines = d.lines(app)
        refused_left = wait_gone(app.pids)
    codes = {(item["name"], item["code"]) for item in problems_of(upgrade_lines)}
    untouched = digest(notes_path) == before_upgrade

    # 4. Roll back: put the backed-up settings file in place, check it byte for byte, start again.
    shutil.copy2(backup / "settings.json", settings_path)
    restored_digest = digest(settings_path)
    with d.app("rollback", env, config="settings.json") as app:
        listening, waited = d.start_ready(app, "restart_rollback", 4)
        after = _notes(app) if waited.state == "ready" else (None, None, [])
        d.stop(app, "restart_rollback", 4)
    checks = [
        d.item("upgrade-refused", refused.state == "exited" and refused.exit_code == 2 and not refused_left,
               code=refused.exit_code),
        d.item("upgrade-named", {("settings_version", "unsupported_version"), ("model_id", "unknown_key"),
                                 ("model", "missing")} <= codes, count=len(codes)),
        d.item("upgrade-data-untouched", untouched),
        d.item("rollback-restored", restored_digest == saved["settings"], digest=saved["settings"]),
        d.item("rollback-ready", waited.state == "ready", ready=ms(waited.elapsed_ms)),
        d.item("rollback-data", after[1] == 3 and after[2] == ["op-1", "op-2", "op-3"]
               and digest(notes_path) == before_upgrade),
    ]
    rows = [["settings.json", saved["settings"], restored_digest, restored_digest == saved["settings"]],
            ["notes.json", before_upgrade, digest(notes_path), digest(notes_path) == before_upgrade]]
    metrics = [d.metric("upgrade-exit-code", refused.exit_code), d.metric("upgrade-problems", len(codes)),
               d.metric("notes-after-rollback", after[1] if after[0] else "—")]
    tally.add(d.report("upgrade", 4, checks, metrics, rows))
    return d.answer("restart_rollback", tally.passed, tally.total)


SCENARIOS = {"config_layers": config_layers, "startup_probe": startup_probe, "logs_secrets": logs_secrets,
             "restart_rollback": restart_rollback}


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs).model_dump()
    secret = new_demo_secret()
    with tempfile.TemporaryDirectory(prefix="local-delivery-") as directory:
        delivery = Delivery(context, Path(directory), secret, values)
        answer = SCENARIOS[values["scenario"]](delivery)
    if logscan.scan_text(answer, delivery.secrets):
        raise SecretLeak("answer")
    return answer
