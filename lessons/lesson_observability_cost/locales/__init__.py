"""Runtime text of observability-cost: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The task: two system prompts and the receipt descriptions, keyed by receipt id.
    # r1 and r4 have the same description on purpose: the baseline sends the same request twice.
    classify_system: str
    batch_system: str
    receipts: dict[str, str]
    # Tool errors.
    unknown_currency: str  # {currency}
    unknown_category: str  # {category}
    # Names shown in reports, keyed by code.
    strategy_names: dict[str, str]
    kind_names: dict[str, str]
    status_names: dict[str, str]
    reason_names: dict[str, str]
    # Values.
    mode_offline: str
    mode_live: str
    value_not_reported: str
    value_not_applicable: str
    value_none: str
    value_empty: str
    tokens_partly_reported: str  # {total} {missing}
    list_separator: str
    # Step ledger report.
    ledger_title: str  # {strategy}
    ledger_summary: str
    offline_note: str
    label_mode: str
    label_model: str
    label_model_calls: str
    label_tool_calls: str
    label_cache_hits: str
    label_end_to_end: str
    label_step_sum: str
    label_total_tokens: str
    label_unreported: str
    label_quality: str
    label_cost: str
    label_note: str
    quality_value: str  # {passed} {total}
    check_quality: str
    check_quality_detail: str  # {passed} {total} {failures}
    failure_item: str  # {receipt} {reason}
    check_usage: str
    check_usage_all: str
    check_usage_missing: str  # {steps}
    cost_none: str
    cost_no_usage: str
    cost_value: str  # {amount} {currency} {model} {source} {date} {covered} {calls}
    columns_ledger: tuple[str, ...]
    # Bottleneck report.
    bottleneck_title: str  # {strategy}
    bottleneck_summary: str
    label_slowest: str
    label_repeated: str
    label_extra_ms: str
    label_extra_tokens: str
    slowest_value: str  # {step} {name} {ms} {share}
    repeat_item: str  # {kind} {name} {count} {steps}
    repeat_cell: str  # {step}
    check_no_repeats: str
    check_no_repeats_ok: str
    check_no_repeats_found: str  # {count}
    columns_bottleneck: tuple[str, ...]
    # Before/after report.
    compare_title: str  # {baseline} {strategy}
    compare_summary: str
    row_quality: str
    row_model_calls: str
    row_tool_calls: str
    row_end_to_end: str
    row_tokens: str
    row_unreported: str
    row_repeats: str
    label_regressions: str
    label_fixes: str
    label_token_change: str
    label_latency_change: str
    check_no_regression: str
    check_no_regression_ok: str
    check_no_regression_found: str  # {items}
    check_failures: str
    check_failures_detail: str  # {before} {after}
    columns_compare: tuple[str, ...]
    # The final answer.
    answer: str  # {strategy} {passed} {total} {calls} {tools} {hits} {ms}
    answer_compare: str  # {baseline} {strategy} {regressions}


texts_for = catalog(__name__, Texts)
