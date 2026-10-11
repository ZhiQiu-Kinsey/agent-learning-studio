"""skills-disclosure runtime text: English."""
from lessons.lesson_skills_disclosure.locales import Texts

TEXTS = Texts(
    vague_description="Helps with studying.",
    task_messages={
        "make_cards": (
            "Turn the study notes below into review cards:\n"
            "A Python list can be changed; a tuple cannot be changed after it is created. A dictionary looks up "
            "values by key, and keys must be immutable, so a tuple can be a key but a list cannot. A set removes "
            "duplicates automatically but does not keep the order of its elements; checking whether an element "
            "is in a set is usually much faster than searching a list."
        ),
        "chat": "Hi! It's Friday today. Say hello to me.",
        "review_question": (
            "Help me review: what is the difference between a Python list and a tuple? "
            "One or two sentences are enough."
        ),
    },
    full_prompt=(
        "You are a study assistant. Below are all the skills you have, each with its full procedure. "
        "When the user's task matches a skill's description, follow its procedure strictly; when none matches, "
        "just answer normally and do not apply a skill."
    ),
    catalog_prompt=(
        "You are a study assistant. The skill catalog below lists only the name and description of each skill. "
        "When the user's task matches a skill's description, first call load_skill to read its full procedure, "
        "then follow it; when none matches, just answer normally and do not load a skill."
    ),
    full_section="## Skill {name}\nDescription: {description}\n\n{body}",
    catalog_heading="Skill catalog:",
    catalog_line="- {name}: {description}",
    load_skill_description="Read the full procedure of one skill. name must be a name listed in the skill catalog.",
    load_skill_name_description="A name from the skill catalog",
    unknown_skill="There is no skill named {name}; the skill catalog has only: {names}.",
    loading_not_applicable="not applicable: all bodies resident",
    loading_none_correct="correct: nothing loaded",
    loading_missed="missed trigger: should have loaded, did not",
    loading_false="false trigger: loaded {names}",
    loading_correct="correct: loaded {names}",
    loading_wrong="wrong skill loaded: {names}",
    card_question_prefixes=("Q:", "Question:"),
    card_answer_prefixes=("A:", "Answer:"),
    format_no_answer="no answer",
    format_cards="{asked} \"Q:\" and {answered} \"A:\" lines; the skill asks for 3–5 cards",
    format_not_cards="not written as review cards",
    format_cards_written="written as {asked} review cards",
    mode_labels={"full": "Full injection", "on_demand": "Catalog + on-demand loading"},
    task_labels={"make_cards": "Make review cards", "chat": "Small talk", "review_question": "Review question"},
    answer_section="[{mode}]\n{answer}",
    no_answer="No answer within {limit} requests.",
    unparsable_arguments="(arguments could not be parsed)",
    value_not_reported="not reported",
    tokens_partly_reported="{total} ({missing} not reported)",
    value_empty="(empty)",
    separator=", ",
    label_task="Task",
    label_description="Description of review-cards",
    value_vague="vague",
    value_precise="precise",
    label_expected="Skill this lesson expects",
    value_expect_none="no skill should be loaded",
    proposals="request {round} proposed {names}",
    proposals_separator="; ",
    value_all_resident="all resident",
    value_no_proposal="no load proposed",
    format_passed="passed: ",
    format_failed="failed: ",
    label_first_tokens="Prompt tokens of request 1 ({mode})",
    check_full_bodies="Full injection: the request carries every skill body",
    check_full_bodies_detail="Found the bodies of {count} skills in the messages actually sent.",
    check_catalog_only="On-demand loading: request 1 has no skill body",
    check_catalog_only_detail="The system prompt of request 1 has {chars} characters and holds only the catalog.",
    check_loading="On-demand loading: loading verdict",
    check_rejected="Unregistered skill names were rejected",
    check_rejected_detail="{names} not in the allowlist; the tool result is a structured error.",
    check_format="{mode}: answer format screen",
    check_format_detail="{detail}. Only the format is checked, not whether the content is right.",
    label_model_calls="Model calls",
    label_note="Learner note",
    title_separator=" and ",
    report_title="{modes}: {task}",
    report_summary=(
        "Prompt tokens come from the usage of each response; what was not reported says \"not reported\". "
        "The loading verdict looks only at load_skill's tool results; the format screen only checks whether "
        "the answer looks like review cards."
    ),
    columns=("Mode", "Model calls", "Prompt tokens per request", "Total prompt tokens", "Loading record",
             "Loading verdict", "Format screen"),
)
