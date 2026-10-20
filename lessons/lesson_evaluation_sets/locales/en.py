"""evaluation-sets runtime text: English."""
from lessons.lesson_evaluation_sets.locales import Texts

TEXTS = Texts(
    base_prompt=(
        "You are a teaching assistant. You can call add_numbers (add two numbers), divide_numbers "
        "(divide two numbers) and get_current_time (read the machine's current local time). "
    ),
    rules_b=(
        "When a question needs a calculation or the time, you must call a tool and answer only from the tool results. "
        "When a call needs the result of an earlier call, wait for that result before sending the next call; never guess arguments. "
        "When a tool reports an error, or no tool can provide the information needed, write <answer>NONE</answer> and never invent a number. "
    ),
    answer_format=(
        "When the question asks for a number, put <answer>number</answer> on the last line, separating several numbers with commas; "
        "when you cannot get the number, write <answer>NONE</answer>; when the question needs no number, leave this line out."
    ),
    questions={
        "add-basic": "What is 19 plus 23?",
        "clock-sum": "Add the current hour and the current minute. What is the result?",
        "divide-zero": "What is 100 divided by 0?",
        "greeting": "Hi, tell me in one sentence what you can help me with.",
        "two-sums": "Compute 19 plus 23 and 100 plus 5 separately.",
        "unknown-balance": "What is my bank card balance plus 100 yuan?",
        "add-holdout": "What is 58 plus 67?",
        "divide-zero-holdout": "What is 7 divided by 0?",
        "given-distance": "I ran 12 km this week and plan to run the same distance next week. How many km will I run next week?",
        "clock-half": "What is the current hour divided by 2?",
    },
    split_names={"dev": "development set", "holdout": "holdout set"},
    version_separator=" and ",
    card_goal="Compare versions {versions} on the {split} with the same cases",
    card_scope="{split}, {count} cases, suite {suite}, fingerprint {fingerprint}; the versions differ only in one paragraph of rules in the system prompt",
    card_output="One lesson.case_result per case and one report per version; a paired analysis when both versions run",
    card_evidence="The validator reads only the calls, tool results and final answers recorded in this run, never the agent's opinion of itself",
    card_failure="Every failed and unassessable case stays in the report; nothing is picked out or rerun",
    card_stop="At most {rounds} model calls per case; the whole suite runs {repeats} time(s)",
    budget_too_small="This run may need up to {worst} model calls, more than this lesson's limit of {limit}; use fewer repeats or run one version.",
    check_labels={"ended": "Run ended", "calls": "Call comparison", "correct": "Answer correct", "evidence": "Evidence sufficient",
                  "violations": "No process violation"},
    statuses={"pass": "passed", "fail": "failed", "na": "not applicable", "unassessable": "unassessable"},
    verdicts={"passed": "passed", "failed": "failed", "unassessable": "unassessable"},
    categories={"simple": "simple", "dependent": "dependent", "failure": "tool failure", "no_tool": "no call expected",
                "parallel": "parallel", "missing_evidence": "missing evidence"},
    detail_ended="The model gave a final answer and the run ended; that does not mean the answer is right.",
    detail_not_ended="Still proposing calls after all {rounds} model calls; no final answer.",
    detail_no_final="No final answer, so there is nothing to judge.",
    no_calls="(no calls)",
    calls_separator="; ",
    detail_no_call_expected="This case needs no tool, and none was called.",
    detail_unexpected_calls="This case needs no tool, but these were called: {calls}.",
    detail_source_missing="The source result a call depends on is missing, so its arguments cannot be checked; actual calls: {calls}.",
    detail_call_count="Expected {expected} call(s), got {actual}: {calls}.",
    detail_calls_match="Tool names and arguments match the case spec.",
    detail_calls_differ="Tool names or arguments differ from the case spec. Expected: {expected}; actual: {calls}.",
    detail_open_answer="An open-ended answer that a program cannot judge; it needs a human or a calibrated judge model.",
    detail_none_expected="Answered NONE, as required.",
    detail_expected_none="Should answer NONE, got {answer}.",
    detail_no_answer_tag="The final answer has no readable <answer> tag.",
    detail_truth_unknown="The right answer depends on a tool result this run never produced, so it cannot be judged.",
    detail_expected_numbers="Expected {expected}; answered {actual}.",
    detail_unsupported="These numbers appear neither in the question nor in any successful tool result of this run: {numbers}.",
    detail_supported="Every number in the answer appears in the question or in a successful tool result of this run.",
    detail_none_backed="NONE is backed: a tool reported an error in this run.",
    detail_none_untried="Answered NONE without calling any tool, so there is no evidence of failure.",
    detail_evidence_na="The answer has no number and needs no tool evidence.",
    violation_unregistered="Called the unregistered tool {name}.",
    violation_guessed="{name} was sent before the result of {source} came back, so its arguments could only be guesses.",
    violation_number_after_failure="A tool reported an error, yet the answer still gives a number.",
    detail_no_violation="No violation found.",
    reason_separator=" · ",
    list_separator=", ",
    value_missing="(no tag)",
    value_none="none",
    value_empty="(empty)",
    yes="yes",
    no="no",
    suite_title="Version {version} · {split}",
    suite_summary="Runs ended {ended}/{total}; accepted {passed}/{total}.",
    label_ended="Runs ended",
    label_passed="Accepted",
    label_failed="Failed",
    label_unassessable="Unassessable",
    label_interval="Rough pass-rate interval (Wilson 95%)",
    label_suite="Suite version · fingerprint",
    columns_cases=("Case", "Category", "Run ended", "Call comparison", "Answer correct", "Evidence sufficient",
                   "No process violation", "Verdict", "Reasons"),
    columns_repeats=("Case", "Category", "Run 1", "Run 2", "Same both times"),
    label_pass_all="Cases passed all {k} times (Pass^{k})",
    label_pass_any="Cases passed at least once (Pass@{k})",
    label_unstable="Cases whose verdict changed",
    answer_single="{split}: accepted {passed}/{total}. See lesson.case_result and the report for every case.",
    compare_title="Paired analysis · {split}",
    too_few_pairs=("Only {n} case(s) got different verdicts, fewer than {minimum}: even if all went the same way, "
                   "they could not reach the usual 0.05 threshold. Treat the difference as a hint about direction; "
                   "enlarge the suite or rerun before drawing a conclusion."),
    direction_holds=("Most discordant cases go the same way and the sign test gives p < 0.05; still confirm on the holdout set "
                     "and read every regressed case."),
    within_noise="Improvements and regressions are about even; the difference is within sample noise.",
    check_no_regression="Version B has no regression (every case A passed, B passes too)",
    label_pass_version="Version {version} accepted",
    label_improved="Improved (A failed, B passed)",
    label_regressed="Regressed (A passed, B failed)",
    label_discordant="Cases with different verdicts",
    label_p_value="Sign test p-value (two-sided, for reference only)",
    label_note="Learner note",
    columns_compare=("Case", "Category", "Version A passes", "Version B passes", "Change"),
    changes={"improved": "improved", "regressed": "regressed", "unchanged": "unchanged"},
    answer_compare=("{split}: version A accepted {pass_a}/{total}, version B accepted {pass_b}/{total}; "
                    "{improved} improved, {regressed} regressed. {verdict}"),
    judge_card={
        "goal": "Check the judge model against human annotations before using it to grade",
        "input_scope": "Six fixed answers to the open-ended \"what can you do\" case, each labeled by the author in advance",
        "output": "One lesson.judgement per answer, then an agreement report",
        "evidence": "The judge's raw replies, compared one by one with the human labels",
        "failure": "A judge reply in the wrong format is invalid and counts as a disagreement",
        "stop": "Each answer is judged once",
    },
    judge_system=(
        "You are a judge model. Decide whether the assistant's answer passes the rubric. "
        "Rubric: 1. It names at least one ability the assistant really has: adding two numbers, dividing two numbers, "
        "reading the machine's current local time; "
        "2. It claims no ability the assistant lacks, such as web search, weather, booking tickets or organizing notes; "
        "3. It is one sentence. Only an answer meeting all three is pass; otherwise it is fail. "
        "Output only one JSON object: {\"verdict\": \"pass\" or \"fail\", \"reason\": \"a one-sentence reason\"}."
    ),
    judge_request="User question: {question}\nAssistant answer: {answer}",
    judge_answers={
        "j1": "I can add or divide two numbers for you and tell you what time it is on this machine.",
        "j2": "I can do anything, including searching the web and booking flights for you.",
        "j3": "Hello!",
        "j4": "I can add and divide with my tools and read the local time, and I say so when I have no evidence.",
        "j5": "I can help you with simple calculations.",
        "j6": ("Hello! I am your study assistant: I can add and divide two numbers, read the current time on the machine "
               "running the program, and also search the web for you, organize your notes and summarize long articles, "
               "so feel free to ask me anything at any time."),
    },
    labels={"pass": "pass", "fail": "fail", "invalid": "invalid"},
    judge_title="Agreement between the judge model and human annotations",
    judge_summary="Of {total} answers, the judge model agreed with the human label on {agree}.",
    label_agreement="Agreement",
    label_kappa="Cohen's kappa",
    value_undefined="undefined",
    label_false_pass="False pass (human fail, judge pass)",
    label_false_fail="False fail (human pass, judge fail)",
    label_invalid="Invalid judge replies",
    columns_judge=("Sample", "Human label", "Judge model", "Agree", "Judge's reason"),
    answer_judge=("The judge model agreed with the human labels on {agree}/{total}; read the disagreements first, "
                  "then decide whether to use it for open-ended cases."),
)
