"""Runtime text of the local-delivery runner: report titles, check labels and details, answers.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale). Ids (check ids,
metric ids, problem codes, phase names) are code and stay the same in every language. The notes app itself
writes its logs in English only: they are a program's output, shown as it is.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Report headings and the column names of each report's table, keyed by report id.
    titles: dict[str, str]
    summaries: dict[str, str]
    columns: dict[str, tuple[str, ...]]
    # One label and one detail per check id; details use named placeholders.
    check_labels: dict[str, str]
    check_details: dict[str, str]
    metric_labels: dict[str, str]
    # Settings problem codes, how a process was stopped, and the three stop modes compared in the lab.
    codes: dict[str, str]
    stop_methods: dict[str, str]
    stop_modes: dict[str, str]
    # Short words that appear in cells and details.
    values: dict[str, str]
    # The final answer of each scenario.
    answers: dict[str, str]


texts_for = catalog(__name__, Texts)
