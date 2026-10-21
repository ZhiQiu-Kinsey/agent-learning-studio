"""What both MCP servers of this lesson share: command line, startup faults and the diagnostics report.

Each server is its own process, started by the runner as ``python -m <module> --locale en``. Stdout is
the protocol channel, so nothing here prints.
"""
import argparse
import os
import re
import time
from typing import TypedDict

from course.i18n import RUNTIME_LOCALES, SOURCE_LOCALE

# Fault injection for restart attempts only: the process really starts, then never becomes usable.
STARTUP_FAULTS = ("exit-on-start", "hang-on-start")
SECRET_LIKE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)


class ServiceInfo(TypedDict):
    pid: int
    loans: int
    env_names: list[str]
    secret_like_env: list[str]


def parse_args(description: str, variants: tuple[str, ...] = ("v1",), argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--locale", choices=RUNTIME_LOCALES, default=SOURCE_LOCALE)
    parser.add_argument("--variant", choices=variants, default=variants[0])
    parser.add_argument("--fault", choices=STARTUP_FAULTS)
    return parser.parse_args(argv)


def apply_startup_fault(fault: str | None):
    if fault == "exit-on-start":
        os._exit(75)  # gone before it reads a single message: the client sees the connection close
    if fault == "hang-on-start":
        # Alive but never reads stdin: only a timeout tells the client; the SDK terminates it on close.
        while True:
            time.sleep(1)


def service_info(loans: int) -> ServiceInfo:
    # Names only, never values: enough to show which variables reached this process.
    names = sorted(os.environ)
    return {"pid": os.getpid(), "loans": loans, "env_names": names,
            "secret_like_env": [name for name in names if SECRET_LIKE.search(name)]}
