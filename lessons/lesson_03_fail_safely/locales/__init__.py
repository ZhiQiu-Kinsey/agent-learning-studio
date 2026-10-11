"""Runtime text of fail-safely: the system prompt, the tool description and tool errors, the answers the runner writes, and the command-line texts.

zh_CN.py and en.py each fill every field. The tool and parameter names are code and stay
the same in every language; only what the model or the learner reads is translated.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The system prompt of the native loop.
    system_prompt: str
    # Tool description (tool_definitions): what the model reads to call divide_numbers.
    divide_numbers: str
    divide_numbers_a: str
    divide_numbers_b: str
    # Tool errors (divide_numbers); they reach the model as structured errors.
    not_a_number: str  # {name}
    not_finite: str
    zero_divisor: str
    out_of_range: str
    # The answer of a fault-injection arm, written by the runner because no model was called.
    fault_answer: str  # {name} {arguments} {error_type} {error}
    # Command-line run (main.py) and the offline demo (offline_demo.py).
    cli_title: str
    cli_examples: tuple[str, ...]
    demo_intro: str
    demo_result: str  # {result}
    demo_cases: dict[str, str]


texts_for = catalog(__name__, Texts)
