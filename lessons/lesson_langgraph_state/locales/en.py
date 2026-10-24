"""langgraph-state runtime text: English."""
from lessons.lesson_langgraph_state.locales import Texts

TEXTS = Texts(
    plan_system=("You are a study-plan assistant. Use the estimate_study_days tool to estimate how many days "
                 "the given lessons take. Pass the lesson ids and the minutes per day exactly as the user gave "
                 "them: do not add or drop lessons, and do not assume a daily time. "
                 "If the tool returns an error, read it and call again once, following the user's original request."),
    request_text="I plan to study these lessons: {lessons}. Daily study time: {minutes}. How many days will it take?",
    lessons_not_given="(not given)",
    minutes_not_given="(not given)",
    tool_description=("Look up lesson ids in this lesson's own table of minutes, divide the total by the minutes "
                      "per day, round up, and return the number of days."),
    tool_lessons_param="List of lesson ids, for example chat-request",
    tool_minutes_param="Minutes of study per day, a positive integer",
    tool_lessons_invalid="lessons must be a non-empty list of lesson ids.",
    tool_minutes_invalid="minutes_per_day must be a positive integer.",
    tool_unknown_lessons="These lessons are not in the table: {unknown}. Lessons you can look up: {known}.",
    problem_text={
        "no_tool_call": "This attempt did not call estimate_study_days, so there is no tool result to check.",
        "tool_error": "The tool returned an error; see the last tool result.",
        "arguments_mismatch": "The lessons or the minutes per day in the tool call differ from the user's request.",
    },
    repair_feedback="The check failed: {problems} Fix the call so it follows the user's original request, then call the tool again.",
    answer_system=("You are a study-plan assistant. Answer only from the tool result you are given: "
                   "in one or two sentences, say how many days it takes and how that was worked out."),
    answer_prompt="Tool result that passed the check: {result}",
    reason_completed="The tool result passed the check and the answer node wrote the answer; the answer text itself was not checked.",
    reason_missing="Missing parameters: {fields}. The program did not assume anything for the user; supply them and run again.",
    reason_failed="The check failed {count} times and the repair budget is spent. Problems on the last attempt: {problems}.",
    answer_needs_input="No estimate yet: {reason}",
    answer_failed="Not done: {reason}",
    answer_stopped=("The graph hit recursion_limit={limit} at step {steps} ({node}); LangGraph raised GraphRecursionError "
                    "and this run got no final state."),
    structure_title="Graph structure",
    structure_summary=("Nodes and edges come from the compiled graph object (get_graph), not from a hand-drawn "
                       "illustration. Conditional edges are chosen by router functions from the state."),
    label_nodes="Nodes",
    label_edges="Edges",
    label_recursion_limit="recursion_limit",
    label_max_repairs="max_repairs",
    edge_direct="direct edge",
    edge_conditional="conditional edge",
    structure_columns=("From", "To", "Kind"),
    report_title="Path of this run",
    report_summary=("The path is recorded as each node runs; each branch comes from the state values its router "
                    "read at that moment. lesson.graph_update is the state update a node wrote back, not a model response."),
    check_terminal="Reached a terminal node",
    detail_terminal="Last node {node}, status={status}: {reason}",
    detail_stopped=("At step {steps} ({node}) the graph hit recursion_limit={limit}; LangGraph raised "
                    "GraphRecursionError and handed back no final state."),
    check_evidence_kept="Evidence was not overwritten",
    detail_evidence_kept="evidence in the state has {evidence} records; the message history has {tool_messages} tool messages.",
    check_answer_days="The answer mentions the number of days the tool computed",
    detail_answer_days="Days computed by the tool: {days}. Only checks that the number appears, not that the wording is right.",
    label_path="Path taken",
    label_steps="Nodes executed",
    label_status="Terminal status",
    label_stop="Why it stopped",
    label_failed_checks="Failed checks",
    label_model_nodes="Runs of nodes that call the model",
    label_note="Learner note",
    value_not_reached="no terminal state reached",
    value_empty="none",
    stop_end="reached END",
    stop_recursion_limit="hit recursion_limit",
    route_columns=("Router at", "State it read", "Sent to"),
)
