"""Text of the remote agent (worker.py) for a2a-delegation, one file per run language.

The worker runs in its own process and gets the run language as ``--locale``: its Agent Card,
status messages and artifact text reach the delegating side as protocol messages, so an English
run must not see Chinese here either.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Agent Card: who this agent is and what its one skill does.
    agent_description: str
    skill_name: str
    skill_description: str
    skill_examples: tuple[str, ...]
    # Status messages that travel with each status update.
    status_received: str  # {count} {chunks}
    status_waiting_index: str  # {seconds}
    status_checked: str  # {claim_id} {evidence}
    status_done: str
    status_failed: str
    status_rejected: str
    status_canceled: str
    # The human-readable part of the artifact.
    artifact_summary: str  # {count}
    superseded_note: str  # {old} {new}


texts_for = catalog(__name__, Texts)
