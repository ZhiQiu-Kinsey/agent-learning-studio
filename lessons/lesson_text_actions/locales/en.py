"""text-actions runtime text: English."""
from lessons.lesson_text_actions.locales import Texts

TEXTS = Texts(
    text_system="""You are a teaching assistant and can use the tool below:
lookup_quiz_score: look up a student's score, number of attempts and update date for their latest quiz. Input JSON: {"student_id": "student ID"}

Write one step at a time, strictly in this format:
Thought: your reasoning
Action: tool name
Action Input: JSON arguments

Stop right after Action Input and wait for the system to give you the Observation. Once you have the Observation and can answer, write:
Thought: your reasoning
Final Answer: your answer to the user""",
    native_system="You are a teaching assistant. Call lookup_quiz_score when you need a student's score; do not guess the data.",
    question=("What did student {student_id} score on their latest quiz? "
              "The pass mark is {pass_line}. Did the student pass?"),
    tool_description="Look up a student's score, number of attempts and update date for their latest quiz.",
    tool_student_id="Student ID, such as s-1042",
    unknown_student="There is no record for student ID {student_id}.",
    invalid_json="Action Input is not valid JSON: {error}",
    not_an_object="Action Input must be a JSON object",
    no_action="Neither an Action nor a Final Answer",
    value_not_reported="not reported",
    row_tool_calls="{count} tool_calls",
    row_text_answer="text answer",
    text_parse_failed="The text protocol got no final answer: parsing failed, so the run stopped.",
    text_no_final="The text protocol got no final answer: no Final Answer within {limit} steps.",
    native_no_answer="Native calling got no final answer within {limit} steps.",
    text_report_title_stop="Text action protocol (with stop)",
    text_report_title_no_stop="Text action protocol (without stop)",
    text_report_summary=(
        "Every model output is parsed and recorded as lesson.parse; a parse failure stops the run with no "
        "guessed repair. The program executes the tool from the parse result, and an Observation the model "
        "wrote itself never enters the context."
    ),
    check_not_leaked="No Observation the model wrote itself entered the later context",
    detail_fabricated="In this run the model wrote {count} Observation(s) itself.",
    check_final_answer="Got a Final Answer",
    detail_no_final="No final answer: the step limit was reached or parsing failed.",
    detail_final_after_observation="The final answer comes from an output written after the model saw the real Observation.",
    native_report_title="Native tool calling",
    native_report_summary="The provider returns the action as structured data in the tool_calls field; the program parses no free text.",
    check_native_answer="Got a final answer",
    detail_native_answer="The final answer comes from an output written after the model saw the tool message.",
    detail_native_unfinished="Not finished within {limit} steps.",
    label_protocol="Protocol",
    label_model_calls="Model calls",
    label_parse_failures="Parse failures",
    label_fabricated="Observations the model wrote",
    label_student="Student ID",
    label_note="Learner note",
    value_empty="(empty)",
    text_columns=("Step", "finish_reason", "Parse result", "Error"),
    native_columns=("Step", "finish_reason", "Model output"),
)
