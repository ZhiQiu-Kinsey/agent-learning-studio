"""Text of the offline test model (fixtures.py) for long-running-tasks, one file per run language.

It holds only the words the scripted replies put into events; the values it reports are read from the injected messages.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    waiting: str  # the jobs are started: say what is awaited
    still_waiting: str  # one result is in, another is not
    gave_up: str  # a job failed twice
    restarted: str  # after cancelling and starting the scan again


texts_for = catalog(__name__, Texts)
