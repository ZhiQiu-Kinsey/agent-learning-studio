"""Runtime text of the mcp-lifecycle runner: the system prompt, call errors and lab reports.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The two servers have their own catalog in locales/servers/. Tool names, service ids and protocol
method names are code and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The agent task.
    agent_system: str
    agent_needs_model: str
    # Why the host refused or failed a call; these become structured tool errors.
    not_routable: str  # {name}
    service_unavailable: str  # {service} {state}
    tool_changed: str  # {name}
    connection_lost: str  # {service} {code} {message}
    write_not_repeated: str  # {status}
    # Status of a write in the host's record, keyed by status code.
    write_status: dict[str, str]
    # Connection states, keyed by state code.
    states: dict[str, str]
    # Lab reports, keyed by task.
    report_titles: dict[str, str]
    outcome_ok: str  # {result}
    outcome_error: str  # {error_type} {error}
    check_reaped: str
    detail_reaped: str  # {pids} {left}
    label_processes_left: str
    # Lifecycle: handshake, names, permissions.
    lifecycle_summary: str  # {services} {routes} {shared}
    check_handshake: str
    detail_handshake: str  # {service} {version} {tools}
    check_identity: str
    detail_identity: str  # {names}
    check_namespaced: str
    detail_namespaced: str  # {shared} {names}
    check_probes: str
    check_bare: str
    check_unregistered: str
    check_write_gate: str
    detail_write_gate: str  # {allowed} {outcome}
    yes_no: tuple[str, str]
    check_no_secret: str
    detail_env: str  # {names}
    label_protocol_version: str
    label_routes: str
    label_hidden: str
    kinds: dict[str, str]
    route_exposed: str
    route_hidden: str
    route_write_off: str
    columns_routes: tuple[str, ...]
    lifecycle_answer: str  # {routes} {refused} {left}
    # Crash and reconnect.
    crash_summary: str  # {attempts} {limit} {fault} {failing}
    check_first_write: str
    check_connection_error: str
    check_bounded: str
    detail_bounded: str  # {attempts} {limit} {state}
    check_state_lost: str
    detail_state_lost: str  # {confirmed} {outcome}
    check_no_replay: str
    check_rechecked: str
    detail_quarantine: str  # {names}
    label_attempts: str
    label_final_state: str
    label_writes: str
    writes_value: str  # {confirmed} {unknown}
    columns_timeline: tuple[str, ...]
    detail_attempt: str  # {attempt}
    detail_fault: str  # {fault}
    detail_recheck: str  # {changed} {added}
    crash_answer: str  # {state} {attempts} {confirmed} {unknown} {left}
    # The agent over two services.
    agent_summary: str  # {rounds} {stop} {attempts}
    stop_reasons: dict[str, str]
    stop_answers: dict[str, str]
    check_model_tools: str
    detail_offered: str  # {round} {names}
    check_lost_not_success: str
    check_writes_recorded: str
    label_model_calls: str
    label_stop_reason: str
    value_none: str


texts_for = catalog(__name__, Texts)
