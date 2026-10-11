"""orchestrator-evaluator runtime text: English."""
from lessons.lesson_orchestrator_evaluator.locales import Texts

TEXTS = Texts(
    notes={
        "messages-context": "The model sees only the messages in this request; the application must resend the history.",
        "application-state": "Application state records the goal and the evidence; the message list does not update it by itself.",
        "context-budget": "When compressing context, keep or drop a tool call and its tool result together.",
    },
    task=("Write one four-option multiple-choice question for each of three lessons: messages-context (Context "
          "components and the message protocol), application-state (Application state and the run lifecycle) and "
          "context-budget (Context budget and the truncation window). Each question must test that lesson's key point."),
    single_system=("You are a quiz writer and write all the questions at once. Output only one JSON array, in the order "
                   "messages-context, application-state, context-budget; each element is "
                   '{"question": "question stem", "options": ["A", "B", "C", "D"], "answer": index of the correct option 0-3, '
                   '"explanation": "why this option is correct"}'),
    orchestrator_system=("You are the orchestrator: you only split the task and do not write questions. Output only JSON: "
                         '{"subtasks": [{"id": "w1", "lesson": "messages-context", "instruction": "a one-sentence instruction for the worker"}]}. '
                         "At most 4 subtasks; lesson can only be messages-context, application-state or context-budget."),
    worker_system=('You are a quiz writer; write only the one question you are given. Output only one JSON object: {"question": "question stem", '
                   '"options": ["A", "B", "C", "D"], "answer": index of the correct option 0-3, "explanation": "why this option is correct"}'),
    evaluator_system=("You are a reviewer. Check a multiple-choice question against the rubric: the stem tests the given key point; "
                      "all four options are plausible but exactly one is correct; the explanation says why it is correct. "
                      'Output only JSON: {"verdict": "pass" or "revise", "feedback": ["a specific problem"]}.'),
    single_request="{task}\nKey points: {notes}",
    worker_request="{instruction}\nKey point: {note}",
    generator_request="Write one multiple-choice question for the {lesson} lesson. Key point: {note}",
    revision_request=("Write one multiple-choice question for the {lesson} lesson. Key point: {note}\n"
                      "Previous version: {previous}\nReview feedback: {feedback}\nPlease revise."),
    review_request="Key point: {note}\nQuestion: {output}",
    no_json="no JSON",
    not_an_object="not a JSON object",
    missing_question="the question stem is missing",
    options_invalid="options must be 4 non-empty strings",
    options_duplicate="the four options must not repeat",
    answer_invalid="answer must be an integer from 0 to 3",
    missing_explanation="the explanation is missing",
    no_json_found="The reply contains no JSON.",
    missing_item="this question is missing",
    format_ok="format passed",
    problem_separator="; ",
    plan_error="The orchestrator's subtask list is malformed",
    plan_reason="subtasks from the orchestrator",
    plan_step="{lesson}: {instruction}",
    no_workers="malformed subtask list; no workers dispatched",
    roles={"single": "single call", "orchestrator": "orchestrator", "worker": "worker", "generator": "generator",
           "evaluator": "evaluator"},
    stop_reasons={"limit": "iteration limit reached", "passed": "review passed",
                  "invalid": "review output in the wrong format", "unchanged": "revision made no change"},
    report_titles={"single": "Single call", "orchestrator": "Orchestrator-workers", "evaluator": "Evaluator-optimizer"},
    report_summary=("A program checks the format; only the evaluator mode asks a model to review question quality. "
                    "Usage adds up only the total_tokens the provider reported."),
    check_format="Every question passes the format check",
    check_format_detail="{ok}/{total} passed",
    label_model_calls="Model calls",
    label_total_tokens="Cumulative total_tokens",
    label_role_calls="Calls per role",
    label_stop_reason="Stop reason",
    label_note="Learner note",
    role_count="{role} {count}",
    role_separator=", ",
    tokens_partly_reported="{total} ({missing} not reported)",
    value_not_reported="not reported",
    value_empty="(empty)",
    columns_single=("Question", "Format check"),
    columns_orchestrator=("Worker", "Format check"),
    columns_evaluator=("Round", "Review source", "Verdict", "Feedback"),
    answer="Model calls: {calls}. Questions that passed the format check: {ok}/{total}.",
    answer_with_stop="Model calls: {calls}. Questions that passed the format check: {ok}/{total}. Stop reason: {reason}.",
)
