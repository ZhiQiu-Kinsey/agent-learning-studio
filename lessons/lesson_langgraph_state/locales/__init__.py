"""Runtime text of langgraph-state: prompts, the tool description and errors, terminal reasons and the reports.

zh_CN.py and en.py each fill every field. Node names, state fields, problem codes and lesson slugs are
code and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The request the planner reads, built from the structured inputs.
    plan_system: str
    request_text: str  # {lessons}, {minutes}
    lessons_not_given: str
    minutes_not_given: str
    # The tool: description, parameter descriptions and business errors.
    tool_description: str
    tool_lessons_param: str
    tool_minutes_param: str
    tool_lessons_invalid: str
    tool_minutes_invalid: str
    tool_unknown_lessons: str  # {unknown}, {known}
    # Verifier feedback that plan reads before a repair: problem code -> sentence.
    problem_text: dict[str, str]
    repair_feedback: str  # {problems}
    # The answer node.
    answer_system: str
    answer_prompt: str  # {result}
    # Terminal reasons written into the state.
    reason_completed: str
    reason_missing: str  # {fields}
    reason_failed: str  # {count}, {problems}
    # The run's answer when the graph did not write one.
    answer_needs_input: str  # {reason}
    answer_failed: str  # {reason}
    answer_stopped: str  # {limit}, {steps}, {node}
    # Report: graph structure.
    structure_title: str
    structure_summary: str
    label_nodes: str
    label_edges: str
    label_recursion_limit: str
    label_max_repairs: str
    edge_direct: str
    edge_conditional: str
    structure_columns: tuple[str, ...]
    # Report: the run.
    report_title: str
    report_summary: str
    check_terminal: str
    detail_terminal: str  # {node}, {status}, {reason}
    detail_stopped: str  # {limit}, {steps}, {node}
    check_evidence_kept: str
    detail_evidence_kept: str  # {evidence}, {tool_messages}
    check_answer_days: str
    detail_answer_days: str  # {days}
    label_path: str
    label_steps: str
    label_status: str
    label_stop: str
    label_failed_checks: str
    label_model_nodes: str
    label_note: str
    value_not_reached: str
    value_empty: str
    stop_end: str
    stop_recursion_limit: str
    route_columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
