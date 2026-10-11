"""reflection-revision runtime text: English."""
from lessons.lesson_reflection_revision.locales import Texts

TEXTS = Texts(
    spec=("A student ID looks like s-1042: a lowercase letter s, a hyphen, and four digits, "
          "where the first digit cannot be 0. The whole string must match."),
    writer_system=('You write Python regular expressions. Output only one JSON object: {"regex": "your regex"}. '
                   "The regex is matched with re.fullmatch, so you do not need ^ and $."),
    self_review_system=("You are a reviewer. Check whether a regex meets the requirement. Output only JSON: "
                        '{"verdict": "pass" or "revise", "issues": ["a problem; leave the list empty if there is none"]}.'),
    draft_request="Requirement: {spec}",
    self_review_request="Requirement: {spec}\nRegex: {pattern}",
    revision_request="Requirement: {spec}\nPrevious regex: {previous}\nReview feedback: {issues}\nPlease revise.",
    pattern_invalid="The regex must be a string of 1–{limit} characters.",
    pattern_not_compiled="The regex does not compile: {error}",
    failure="{text} should {expected}, but it {actual}",
    expected_words={"match": "match", "no_match": "not match"},
    actual_words={"match": "matched", "no_match": "did not match"},
    no_json_object="The reply contains no JSON object.",
    json_not_object="The JSON in the reply is not an object.",
    missing_regex="The JSON has no string field regex",
    stop_reasons={"limit": "iteration limit reached", "passed": "review passed",
                  "invalid": "review output in the wrong format", "unchanged": "revision made no change"},
    reviewer_names={"tests": "tests", "self": "model self-review"},
    issue_separator="; ",
    report_titles={"self": "Model self-review drives revision", "tests": "Test results drive revision"},
    report_summary=("The final version is always checked against the same real test cases; "
                    "a review that says pass does not mean the tests pass."),
    check_final="Final version passes every test case",
    final_detail="{passed}/{total} passed",
    final_detail_error="{passed}/{total} passed; {error}",
    label_stop_reason="Stop reason",
    label_iterations="Iterations",
    label_max_iters="Iteration limit",
    label_model_calls="Model calls",
    label_total_tokens="Cumulative total_tokens",
    label_final_regex="Final regex",
    label_note="Learner note",
    tokens_partly_reported="{total} ({missing} not reported)",
    value_not_reported="not reported",
    value_empty="(empty)",
    table_columns=("Iteration", "Regex under review", "Review source", "Verdict", "Feedback"),
    answer_passed="Stop reason: {reason}. The final regex {pattern} passed the real test cases ({passed}/{total}).",
    answer_failed="Stop reason: {reason}. The final regex {pattern} failed the real test cases ({passed}/{total}).",
)
