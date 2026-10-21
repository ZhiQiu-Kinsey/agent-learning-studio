"""Layered settings of the notes app: defaults, then the settings file, then the environment.

The app and the delivery checks share this module, so the checks predict exactly what the app will resolve.
Only the standard library is imported: the app starts as a separate process and must come up fast.

Rules the lesson relies on:
- every problem is collected and reported by name and code, never with the offending value (a value may be a secret);
- a credential is read from the environment only; a settings file that carries one is refused, not trusted;
- unknown keys in the file are refused (a typo must not silently fall back to a default);
- an unknown NOTES_* variable is only a warning: the environment also carries unrelated names.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

VERSION = "1.0.0"
SETTINGS_VERSION = 1
ENV_PREFIX = "NOTES_"
# Only the IPv4 loopback address is allowed: the app is for one learner on this machine.
LOOPBACK_HOST = "127.0.0.1"
LEVELS = ("debug", "info", "warning", "error")
SECRET_LIKE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)
SOURCES = ("default", "file", "env")  # lowest to highest precedence


@dataclass(frozen=True)
class Setting:
    name: str
    kind: str  # "str" | "int" | "choice"
    default: Any = None
    required: bool = False
    secret: bool = False
    choices: tuple = ()
    low: int = 0
    high: int = 0

    @property
    def env(self) -> str:
        return ENV_PREFIX + self.name.upper()


SETTINGS = (
    Setting("host", "str", default=LOOPBACK_HOST),
    Setting("port", "int", default=0, low=0, high=65535),  # 0: let the system pick a free port
    Setting("model", "str", required=True),
    Setting("api_key", "str", required=True, secret=True),
    Setting("log_level", "choice", default="info", choices=LEVELS),
    Setting("max_notes", "int", default=100, low=1, high=1000),
    Setting("data_dir", "str", default="data"),
)
BY_NAME = {setting.name: setting for setting in SETTINGS}


@dataclass(frozen=True)
class Problem:
    """What is wrong, by setting name and code. No value is ever attached."""
    name: str
    code: str  # missing | invalid | unknown_key | secret_in_file | unsupported_version | file_unreadable

    def as_dict(self) -> dict:
        return {"name": self.name, "code": self.code}


class SettingsError(Exception):
    def __init__(self, problems: list[Problem]):
        super().__init__(", ".join(f"{problem.name}:{problem.code}" for problem in problems))
        self.problems = problems


@dataclass(frozen=True)
class Resolved:
    values: dict[str, Any]
    sources: dict[str, str]  # setting name -> default | file | env
    warnings: tuple[Problem, ...] = ()

    def public(self) -> list[dict]:
        """One row per setting: where it came from and whether it is set. A secret never shows its value."""
        rows = []
        for setting in SETTINGS:
            row = {"name": setting.name, "source": self.sources[setting.name],
                   "set": self.values.get(setting.name) not in (None, ""), "secret": setting.secret}
            if not setting.secret:
                row["value"] = self.values.get(setting.name)
            rows.append(row)
        return rows


def _parse(setting: Setting, raw: Any) -> Any:
    """Return the typed value or raise ValueError; the message is never shown, so it may stay generic."""
    if setting.kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            raise ValueError("not an integer")
        value = int(raw)
        if not setting.low <= value <= setting.high:
            raise ValueError("out of range")
        return value
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 512:
        raise ValueError("not a usable string")
    value = raw.strip()
    if setting.kind == "choice" and value not in setting.choices:
        raise ValueError("not an allowed choice")
    if setting.name == "host" and value != LOOPBACK_HOST:
        raise ValueError("only the loopback address is allowed")
    if setting.name == "data_dir" and (Path(value).is_absolute() or ".." in Path(value).parts):
        raise ValueError("must be a relative path inside the working directory")
    return value


def read_file(path: Path | None) -> tuple[dict[str, Any], list[Problem]]:
    """Read the settings file; unusable content becomes problems, not exceptions."""
    if path is None:
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, [Problem("settings_file", "file_unreadable")]
    if not isinstance(data, dict):
        return {}, [Problem("settings_file", "file_unreadable")]
    problems = []
    if data.get("settings_version") != SETTINGS_VERSION:
        problems.append(Problem("settings_version", "unsupported_version"))
    values = {}
    for key, raw in data.items():
        if key == "settings_version":
            continue
        setting = BY_NAME.get(key)
        if setting is None:
            problems.append(Problem(key, "unknown_key"))
        elif setting.secret:
            problems.append(Problem(key, "secret_in_file"))
        else:
            values[key] = raw
    return values, problems


def load_settings(path: Path | None, env: Mapping[str, str]) -> Resolved:
    """Resolve every setting; raise SettingsError listing all problems when any value is unusable or missing."""
    file_values, problems = read_file(path)
    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for setting in SETTINGS:
        layers = [("default", setting.default)] if setting.default is not None else []
        if setting.name in file_values:
            layers.append(("file", file_values[setting.name]))
        if env.get(setting.env, "") != "":
            layers.append(("env", env[setting.env]))
        if not layers:
            sources[setting.name] = "default"
            if setting.required:
                problems.append(Problem(setting.name, "missing"))
            continue
        source, raw = layers[-1]  # the highest layer wins; a bad value is not replaced by a lower layer's
        try:
            values[setting.name] = _parse(setting, raw)
            sources[setting.name] = source
        except ValueError:
            sources[setting.name] = source
            problems.append(Problem(setting.name, "invalid"))
    if problems:
        raise SettingsError(problems)
    known = {setting.env for setting in SETTINGS}
    warnings = tuple(Problem(name, "unknown_env") for name in sorted(env)
                     if name.startswith(ENV_PREFIX) and name not in known)
    return Resolved(values, sources, warnings)


def secret_values(env: Mapping[str, str]) -> dict[str, str]:
    """The credential values present in an environment, by setting name; used to scan logs and reports."""
    return {setting.name: env[setting.env] for setting in SETTINGS
            if setting.secret and env.get(setting.env, "") != ""}
