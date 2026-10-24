"""Runtime text of evaluation-sets: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py and verifier.py read them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The agent under test: the shared prompt, the rules only version B adds, the shared answer format.
    base_prompt: str
    rules_b: str
    answer_format: str
    # The question of every case, keyed by case id (cases.py).
    questions: dict[str, str]
    # The task card of a comparison run.
    split_names: dict[str, str]
    version_separator: str
    card_goal: str  # {versions} {split}
    card_scope: str  # {split} {count} {suite} {fingerprint}
    card_output: str
    card_evidence: str
    card_failure: str
    card_stop: str  # {rounds} {repeats}
    budget_too_small: str  # {worst} {limit}
    # Verifier: check labels, statuses and the detail of each outcome.
    check_labels: dict[str, str]
    statuses: dict[str, str]
    verdicts: dict[str, str]
    categories: dict[str, str]
    detail_ended: str
    detail_not_ended: str  # {rounds}
    detail_no_final: str
    no_calls: str
    calls_separator: str
    detail_no_call_expected: str
    detail_unexpected_calls: str  # {calls}
    detail_source_missing: str  # {calls}
    detail_call_count: str  # {expected} {actual} {calls}
    detail_calls_match: str
    detail_calls_differ: str  # {calls}
    detail_open_answer: str
    detail_none_expected: str
    detail_expected_none: str  # {answer}
    detail_no_answer_tag: str
    detail_truth_unknown: str
    detail_expected_numbers: str  # {expected} {actual}
    detail_unsupported: str  # {numbers}
    detail_supported: str
    detail_none_backed: str
    detail_none_untried: str
    detail_evidence_na: str
    violation_unregistered: str  # {name}
    violation_guessed: str  # {name} {source}
    violation_number_after_failure: str
    detail_no_violation: str
    reason_separator: str
    list_separator: str
    value_missing: str
    value_none: str
    value_empty: str
    word_yes: str
    word_no: str
    # The report of one version.
    suite_title: str  # {version} {split}
    suite_summary: str  # {ended} {passed} {total}
    label_ended: str
    label_passed: str
    label_failed: str
    label_unassessable: str
    label_interval: str
    label_suite: str
    columns_cases: tuple[str, ...]
    columns_repeats: tuple[str, ...]
    label_pass_all: str  # {k}
    label_pass_any: str  # {k}
    label_unstable: str
    answer_single: str  # {split} {passed} {total}
    # The paired comparison.
    compare_title: str  # {split}
    too_few_pairs: str  # {n} {minimum}
    direction_holds: str
    within_noise: str
    check_no_regression: str
    label_pass_version: str  # {version}
    label_improved: str
    label_regressed: str
    label_discordant: str
    label_p_value: str
    label_note: str
    columns_compare: tuple[str, ...]
    changes: dict[str, str]
    answer_compare: str  # {split} {pass_a} {pass_b} {total} {improved} {regressed} {verdict}
    # Judge calibration: the rubric, the fixed answers, and the agreement report.
    judge_card: dict[str, str]
    judge_system: str
    judge_request: str  # {question} {answer}
    judge_answers: dict[str, str]
    labels: dict[str, str]
    judge_title: str
    judge_summary: str  # {agree} {total}
    label_agreement: str
    label_kappa: str
    value_undefined: str
    label_false_pass: str
    label_false_fail: str
    label_invalid: str
    columns_judge: tuple[str, ...]
    answer_judge: str  # {agree} {total}


texts_for = catalog(__name__, Texts)
