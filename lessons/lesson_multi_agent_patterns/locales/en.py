"""multi-agent-patterns runtime text: English."""
from lessons.lesson_multi_agent_patterns.locales import Texts

TEXTS = Texts(
    docs={
        "d1": ("When routing, the model outputs only one label. If the first line of the reply is not an allowed label, "
               "the ticket takes the fallback label other and the raw reply is kept."),
        "d2": ("A program checks the orchestrator's subtasks first. There can be at most 4 subtasks; with more, "
               "the whole list is discarded and no worker is dispatched."),
        "d3": ("The evaluator-optimizer iteration limit max_iters is at most 3. If a revision is identical to the "
               "previous version, the loop stops early."),
        "d4": "The orchestrator splits a task into at most 6 subtasks, and all workers run in parallel.",
    },
    doc_titles={
        "d1": "Class notes: workflow patterns",
        "d2": "Class notes: orchestrator-workers",
        "d3": "Class notes: the revision loop",
        "d4": "Extra notes: orchestrator-workers",
    },
    doc_block="[{id}] {title}\n{text}",
    topic_names={
        "fallback_label": "the routing fallback label",
        "worker_cap": "the orchestrator's subtask limit",
        "max_iters": "the revision loop's iteration limit",
    },
    task_brief=("Task: write 3 multiple-choice questions with four options for learners, one for each topic: "
                "fallback_label (the routing fallback label), worker_cap (the orchestrator's subtask limit), "
                "max_iters (the revision loop's iteration limit).\n"
                "Write each question as JSON: {\"topic\": topic, \"question\": stem, \"options\": [4 options], "
                "\"answer\": index of the correct option 0 to 3, \"evidence\": {\"doc\": document id, \"quote\": text from the document}}.\n"
                "Requirements: the quote must be copied word for word from the document named in doc; "
                "the correct option must state the value given in the documents."),
    outdated_rule=("Rule: d4 is an old draft and out of date. Where it conflicts with the other documents, "
                   "the other documents win; never use it as evidence."),
    research_instruction=("This step is research: for each topic, find the value and the exact text in the documents. "
                          "Output only JSON: {\"facts\": [{\"topic\": topic, \"value\": value, \"doc\": document id, "
                          "\"quote\": text from the document}]}. Leave out topics the documents do not cover."),
    write_instruction=("This step is writing: from the list of facts, write one question per topic. "
                       "Output only JSON: {\"questions\": [...]}, each question in the format given in the task."),
    review_instruction=("This step is review: check for each question that the quote is copied word for word from "
                        "its document and that the correct option states the documented value; fix any problem. "
                        "Output only JSON: {\"verdict\": \"pass\" or \"revised\", \"questions\": [...]}."),
    single_instruction=("Do it all at once: check the documents, then write the questions. "
                        "Output only JSON: {\"questions\": [...]}, each question in the format given in the task."),
    docs_header="Documents:",
    facts_header="List of facts (JSON):",
    questions_header="Questions to review (JSON):",
    single_system="You are a course assistant who writes questions for learners from the documents given.",
    role_prompts={
        "researcher": "You are a researcher. You only find facts in the documents; you do not write questions.",
        "writer": "You are a question writer. You write questions only from the facts you are given; you look up nothing else.",
        "reviewer": "You are a reviewer. You only check the evidence of each question and fix questions when needed.",
    },
    verifier_not_list="The verifier needs a list of questions; what it received is not a list",
    problem_labels={
        "format": "The question is malformed (stem, 4 distinct options, answer an integer from 0 to 3)",
        "quote_not_found": "The quote does not appear word for word in the document it names",
        "outdated_source": "The evidence comes from d4, the out-of-date old draft",
        "wrong_answer": "The correct option does not state the documented value, or another option states it too",
        "missing": "No question for this topic",
        "duplicate": "More than one question for this topic",
    },
    plan_reason="Task graph: who does which step in which context; everything ends at the same program verifier.",
    plan_step="{agent} · {role}: {detail}",
    plan_details={
        "solo": "reads the four documents, writes and self-checks, one request",
        "research_all": "fresh request: task, rule and all documents; returns a list of facts",
        "write_from_facts": "fresh request: gets only the previous step's list of facts and writes",
        "review_with_docs": "fresh request: all documents and the draft; checks each question",
        "stage_research": "one shared message history, researcher prompt in place",
        "stage_write": "one shared message history, writer prompt in place; sees the research reply",
        "stage_review": "one shared message history, reviewer prompt in place; sees both earlier stages",
        "research_shard": "own context, sees only document {docs}, in parallel with the other researchers",
        "merge": "merges the facts and records duplicates and conflicts; settles nothing",
        "write_merged": "own context: the handoff and the merged facts, no documents",
        "review_cited": "own context: the handoff, the draft and the documents the draft cites",
        "verify": "program verifier: the same acceptance set",
    },
    mode_names={"single": "Single agent", "workflow": "Fixed workflow", "roles": "Role switching",
                "multi": "Independent agents"},
    role_names={"assistant": "assistant", "researcher": "researcher", "writer": "writer", "reviewer": "reviewer",
                "program": "program"},
    handoff_names={"minimal": "Minimal handoff: the task and the assigned documents",
                   "with_rules": "Handoff with rules: plus the old-draft rule"},
    handoff_not_used="Not used: only independent agents get a handoff",
    report_summary=("All four modes do the same task and hand their final questions to the same program verifier; "
                    "usage is only the total_tokens the provider reported, and wall-clock time is measured on the "
                    "backend. Each table row is one model call and what its context really held."),
    check_topic="Topic {topic}: {name}",
    check_ok="The evidence checks out and the correct option states the documented value",
    check_verifier="Verifier ran",
    label_task="Task acceptance",
    value_task="{passed}/{total} topics passed",
    label_model_calls="Model calls",
    label_total_tokens="Total total_tokens",
    value_not_reported="not reported",
    tokens_partly_reported="{total} (calls not reported: {missing})",
    label_wall_ms="Wall-clock time (ms)",
    label_identities="Run identities and roles",
    value_identities="run identities: {identities}; roles: {roles}",
    label_input_chars="Input characters in total",
    label_conflicts="Merge conflicts (topics with contradicting values)",
    label_duplicates="Topics researched more than once",
    label_handoff="Handoff",
    label_note="Learner note",
    value_empty="(empty)",
    value_yes="yes",
    value_no="no",
    value_none="none",
    list_separator=", ",
    ledger_columns=("Run identity", "Role", "Branch", "Round", "Messages", "Input characters", "Documents seen",
                    "Sees old-draft rule", "total_tokens", "Time (ms)"),
    merge_detail="Topics researched by more than one researcher: {duplicates}; topics with contradicting values: {conflicts}.",
    answer="{mode}: {passed}/{total} topics passed the verifier; model calls: {calls}; wall-clock time: {wall} ms.",
)
