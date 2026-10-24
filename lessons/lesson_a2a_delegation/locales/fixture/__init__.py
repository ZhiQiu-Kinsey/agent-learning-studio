"""Text of the offline test model (fixtures.py) for a2a-delegation, one file per run language.

It holds only what the scripted replies put into events: the claims of the scripted delegation and the
answer templates that quote the real tool result.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    claims: tuple[str, ...]
    answer: str  # {lines}
    claim_line: str  # {claim_id} {claim} {chunks}
    superseded: str  # {chunks}
    line_separator: str
    not_delegated: str  # {error_type} {error}


texts_for = catalog(__name__, Texts)
