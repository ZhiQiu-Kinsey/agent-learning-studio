"""Runtime text: English."""
from lessons.lesson_observability_cost.locales import Texts

TEXTS = Texts(
    classify_system=(
        "You are checking travel expense claims. Put the one expense description the user gives into one of three "
        "categories: transport, lodging, meals. "
        "Output only one JSON object, for example {\"category\": \"transport\"}, and nothing else."
    ),
    batch_system=(
        "You are checking travel expense claims. The user gives a JSON array; each item has an id and a description. "
        "Put each item into one of three categories: transport, lodging, meals. "
        "Output only one JSON array whose items look like {\"id\": \"r1\", \"category\": \"transport\"}, in the input order, and nothing else."
    ),
    receipts={
        "r1": "Taxi from the airport to the hotel",
        "r2": "Hotel room for two nights during the conference",
        "r3": "Working lunch with a client",
        "r4": "Taxi from the airport to the hotel",
    },
    unknown_currency="The rate table has no currency {currency}.",
    unknown_category="There is no category {category}; it must be transport, lodging or meals.",
    strategy_names={"baseline": "Baseline: one request per receipt, no cache", "tool_cache": "Tool cache only",
                    "batched": "Batched request only"},
    kind_names={"llm": "model request", "tool": "tool call", "cache": "cache hit"},
    status_names={"ok": "ok", "error": "failed"},
    reason_names={
        "ok": "passed",
        "unparsed": "the model reply could not be parsed",
        "tool_error": "a tool returned an error",
        "wrong_category": "the category differs from the human label",
        "wrong_amount": "the amount differs from the human label",
    },
    mode_offline="offline test mode",
    mode_live="real run",
    value_not_reported="not reported",
    value_not_applicable="—",
    value_none="none",
    value_empty="(empty)",
    tokens_partly_reported="{total} ({missing} more not reported)",
    list_separator="; ",
    ledger_title="Step ledger · {strategy}",
    ledger_summary=(
        "Each row is one span: a model request, a tool call or a cache hit. The runner times each call from just before "
        "to just after it; token counts are copied from the usage in each response, and a response without them reads "
        "\"not reported\". The step number is the event round; a tool row's correlation ID is the id of its tool_call event."
    ),
    offline_note=("This is offline test mode: the model replies and the usage come from the test fixture, only to check "
                  "the program; they stand for no provider."),
    label_mode="Run mode",
    label_model="Model",
    label_model_calls="Model calls",
    label_tool_calls="Tool calls",
    label_cache_hits="Cache hits",
    label_end_to_end="End-to-end time (ms)",
    label_step_sum="Sum of step times (ms)",
    label_total_tokens="Reported tokens in total",
    label_unreported="Model calls with usage not reported",
    label_quality="Question set passed",
    label_cost="Estimated cost",
    label_note="Learner note",
    quality_value="{passed}/{total}",
    check_quality="Category and amount match the human labels",
    check_quality_detail="{passed}/{total} match. {failures}",
    failure_item="{receipt}: {reason}",
    check_usage="Every model call reported usage",
    check_usage_all="Every response carries usage.",
    check_usage_missing=("The responses of steps {steps} carry no usage; their tokens are not reported and are left out "
                         "of the total."),
    cost_none="Not converted: no price source and date given",
    cost_no_usage="Cannot convert: no model call reported usage",
    cost_value=(
        "About {amount} {currency} (an estimate, not a bill). Model {model}; prices from {source}, {date}; "
        "covers {covered}/{calls} model calls; cache-hit prices are not distinguished."
    ),
    columns_ledger=("Step", "Kind", "Name", "Receipt", "Correlation ID", "Fingerprint", "Time ms", "Input tokens",
                    "Output tokens", "Status", "Repeat"),
    bottleneck_title="Bottlenecks: slow steps and repeated calls · {strategy}",
    bottleneck_summary=(
        "Executed spans ranked by time, slowest first; a cache hit is not an execution. The same fingerprint means a "
        "repeat: the same tool with the same arguments, or a model request body identical to the character."
    ),
    label_slowest="Slowest step",
    label_repeated="Repeated executions",
    label_extra_ms="Time spent on repeats (ms)",
    label_extra_tokens="Tokens spent on repeated requests",
    slowest_value="Step {step} {name}: {ms} ms, {share} of end-to-end",
    repeat_item="{kind} {name} ran {count} times, in steps {steps}",
    repeat_cell="same as step {step}",
    check_no_repeats="No call was executed twice",
    check_no_repeats_ok="Every fingerprint ran once.",
    check_no_repeats_found="Fingerprints that ran more than once: {count}; see the Repeat column in the table.",
    columns_bottleneck=("Rank", "Step", "Kind", "Name", "Time ms", "Share of end-to-end", "Repeat"),
    compare_title="Before and after: {baseline} → {strategy}",
    compare_summary=("Both passes use the same four receipts and the same human labels. Check first whether quality "
                     "dropped, then what was saved."),
    row_quality="Question set passed",
    row_model_calls="Model calls",
    row_tool_calls="Tool calls",
    row_end_to_end="End-to-end time (ms)",
    row_tokens="Reported tokens in total",
    row_unreported="Model calls with usage not reported",
    row_repeats="Repeated executions",
    label_regressions="Passed before, failed after",
    label_fixes="Failed before, passed after",
    label_token_change="Token change",
    label_latency_change="End-to-end time change (ms)",
    check_no_regression="Quality did not drop",
    check_no_regression_ok="No item of the question set went from passed to failed.",
    check_no_regression_found="Passed before, failed after: {items}",
    check_failures="Failures did not increase",
    check_failures_detail="Failed items {before} → {after}.",
    columns_compare=("Measure", "Baseline", "After", "Change"),
    answer=(
        "Checked {total} receipts with \"{strategy}\": {passed}/{total} match the human labels; "
        "model calls: {calls}, tool calls: {tools}, cache hits: {hits}, {ms} ms end to end."
    ),
    answer_compare="Comparing \"{baseline}\" with \"{strategy}\": {regressions}",
)
