"""Reading the app's log back: is it structured, what does it say about startup, and does it leak a credential?

The scan is the gate the lesson is about. It knows the credential values the check handed to the app, looks for
them in every log line, and reports only the line number, the event name and *which* setting leaked, never the
value. Anything shown to a learner goes through ``redact`` first.
"""
import json
from dataclasses import dataclass

REQUIRED_FIELDS = ("ts", "level", "event")
LIFECYCLE = ("start", "config_loaded", "listening", "ready", "shutdown_requested", "stopped")


@dataclass(frozen=True)
class LogLine:
    number: int
    text: str
    record: dict | None  # None when the line is not a JSON object


@dataclass(frozen=True)
class Leak:
    line: int
    event: str | None
    setting: str  # the name of the setting whose value appeared, e.g. api_key


def parse(text: str) -> list[LogLine]:
    lines = []
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            record = None
        lines.append(LogLine(number, raw, record if isinstance(record, dict) else None))
    return lines


def structured(lines: list[LogLine]) -> bool:
    """Every line is a JSON object with ts, level and event: a machine can filter and count them."""
    return bool(lines) and all(line.record is not None and all(key in line.record for key in REQUIRED_FIELDS)
                               for line in lines)


def events(lines: list[LogLine]) -> list[str]:
    return [line.record["event"] for line in lines if line.record and isinstance(line.record.get("event"), str)]


def find(lines: list[LogLine], event: str) -> dict | None:
    for line in lines:
        if line.record and line.record.get("event") == event:
            return line.record
    return None


def lifecycle_in_order(lines: list[LogLine]) -> bool:
    """The lifecycle events appear, each after the one before it (other events may sit in between)."""
    names = iter(events(lines))
    return all(any(name == wanted for name in names) for wanted in LIFECYCLE)


def leaks(lines: list[LogLine], secrets: dict[str, str]) -> list[Leak]:
    found = []
    for line in lines:
        for setting, value in secrets.items():
            if value and value in line.text:
                found.append(Leak(line.number, line.record.get("event") if line.record else None, setting))
    return found


def scan_text(text: str, secrets: dict[str, str]) -> list[str]:
    """Names of the settings whose value appears anywhere in a text (a settings file, a response body)."""
    return sorted(setting for setting, value in secrets.items() if value and value in text)


def redact(text: str, secrets: dict[str, str]) -> str:
    """Replace every credential value by a marker that names the setting, so the text can be shown."""
    for setting, value in secrets.items():
        if value:
            text = text.replace(value, f"[REDACTED:{setting}]")
    return text
