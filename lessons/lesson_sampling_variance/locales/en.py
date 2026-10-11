"""sampling-variance runtime text: English."""
from lessons.lesson_sampling_variance.locales import Texts

TEXTS = Texts(
    default_question="Suggest a name for a small shop that sells cat supplies.",
    system_prompt="You suggest names. Output only one shop name, with no explanation and no punctuation.",
    missing_choices="The model response has no choices[0], so there is no answer to read.",
    answer=("Sent the same request {repeats} times and got {distinct} distinct answers "
            "(compared character by character after trimming leading and trailing whitespace)."),
    report_title="temperature={temperature}: {repeats} answers",
    report_summary=("The same request body was sent unchanged; every answer comes from its own response. "
                    "Distinct answers are counted character by character after trimming leading and trailing whitespace."),
    label_temperature="temperature",
    label_repeats="Repeats",
    label_distinct="Distinct answers",
    label_most_common="Most frequent answer",
    label_prompt_total="Prompt tokens, total",
    label_completion_total="Completion tokens, total",
    label_total_total="Total tokens, total",
    value_times="{count} times",
    value_not_reported="not reported",
    column_number="#",
    column_answer="Answer",
    column_completion_tokens="Completion tokens",
)
