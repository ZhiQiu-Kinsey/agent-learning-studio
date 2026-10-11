"""Runtime text of tools.py: tool descriptions and tool error messages.

tools.py is shared by tool-proposals, tool-selection and dependent-calls, so its text
has its own catalog. Tool and parameter names are code and stay the same in every
language; only the descriptions the model reads and the error messages are translated.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Tool descriptions (tool_definitions): what the model reads to pick a tool.
    add_numbers: str
    add_numbers_a: str
    add_numbers_b: str
    get_current_time: str
    # Tool errors (add_numbers); they reach the model as structured errors.
    not_a_number: str  # {name}
    not_finite: str


texts_for = catalog(__name__, Texts)
