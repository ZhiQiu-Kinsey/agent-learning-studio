"""Runtime text of multi-turn-history: the system prompt, the scripted turns and the lab report.

zh_CN.py and en.py each fill every field. The Code scene annotates system_prompt, turns
and fact line by line, so those fields keep the same number of lines in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Sent to the model: the system prompt and the question of each turn.
    system_prompt: str
    turns: tuple[str, ...]
    # The fact stated in turn 1; the report looks for it in what turn 2 sent and answered.
    fact: str
    # Error when the response has no choices[0].
    missing_choices: str
    # Lab report.
    report_title: str
    summary_full: str
    summary_latest_only: str
    check_fact_sent: str
    check_fact_sent_detail: str  # {fact}
    check_fact_answered: str
    check_fact_answered_detail: str
    label_mode: str
    mode_values: dict[str, str]
    label_model_calls: str
    label_last_message_count: str
    label_prompt_growth: str
    prompt_growth: str  # {first} {last}
    label_note: str
    columns: tuple[str, ...]
    value_yes: str
    value_no: str
    value_not_reported: str
    value_empty: str


texts_for = catalog(__name__, Texts)
