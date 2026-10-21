"""Runtime text of mcp-basics: everything the server and the runner send to the model or put into events.

zh_CN.py and en.py each fill every field. server.py reads them with the --locale it was started with,
runtime.py with texts_for(context.locale). Tool names, argument names and protocol method names are code
and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The MCP server: tool and parameter descriptions, business errors.
    search_description: str
    query_description: str
    top_k_description: str
    read_description: str
    chunk_id_description: str
    status_description: str
    empty_query: str
    unknown_chunk: str  # {chunk_id}
    # The agent task: system prompt, and why it cannot run without a model.
    agent_system: str
    agent_needs_model: str
    # Lab reports, keyed by task.
    report_titles: dict[str, str]
    # Discovery and calls.
    tour_summary: str  # {version} {method} {tools}
    check_handshake: str
    detail_handshake: str  # {method} {version}
    check_discovered: str
    check_hit: str
    detail_hit: str  # {error} {count} {first}
    check_miss: str
    detail_miss: str  # {error} {count}
    check_no_secret: str
    detail_env: str  # {names}
    label_protocol_version: str
    label_tool_count: str
    label_server_pid: str
    columns_tools: tuple[str, ...]
    tour_answer: str  # {version} {tools} {hits} {misses}
    # Error paths, keyed by path code; the layer that answered, keyed by layer code.
    paths: dict[str, str]
    layers: dict[str, str]
    detail_layer: str  # {expected} {seen}
    errors_summary: str  # {fault}
    label_fault: str
    fault_value: str  # {fault}
    columns_errors: tuple[str, ...]
    errors_answer: str  # {tool_errors} {protocol_errors}
    # The agent over MCP: who did what, and why the loop stopped.
    agent_summary: str  # {found} {offered} {proposals} {calls} {stop}
    stop_reasons: dict[str, str]
    check_host_filter: str
    detail_host_filter: str  # {offered} {hidden}
    check_calls_over_mcp: str
    detail_calls_over_mcp: str  # {proposals} {calls}
    label_model_calls: str
    label_mcp_calls: str
    label_stop_reason: str
    columns_duties: tuple[str, ...]
    duties: dict[str, str]
    owners: dict[str, str]
    value_none: str
    stop_answers: dict[str, str]


texts_for = catalog(__name__, Texts)
