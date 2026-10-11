"""persistent-memory runtime text: English."""
from lessons.lesson_10_persistent_memory.locales import Texts

TEXTS = Texts(
    question="What learning goal did I set earlier?",
    seed_value="Understand an agent's messages and state",
    seed_source="sample seeded by the offline test",
    no_text_answer="The model returned no text answer.",
    storage_temporary="temporary SQLite (offline test)",
    storage_local="fixed local SQLite",
    label_note="Learner note",
    label_model_calls="Model calls",
    label_storage="Storage",
    value_none="none",
    value_yes="yes",
    value_no="no",
    separator=", ",
    columns_steps=("Step", "Namespace", "Value", "Source", "Version"),
    reopen_title="Save and reopen the connection",
    reopen_summary=(
        "The first connection writes and closes; a second, new connection reads back by the same namespace and key. "
        "No model was called."
    ),
    reopen_check_value="The value read after reopening matches what was written",
    reopen_check_value_detail="The read happens after the first connection closed; value and version are compared.",
    reopen_check_other="The same key in another namespace was not changed by this write",
    reopen_check_other_detail=(
        "Compares what {other} returned before and after the write. "
        "A namespace is only a query partition, not access control."
    ),
    label_version_after="Version after the write",
    row_first_write="First connection writes",
    row_second_read="Second connection reads back",
    row_other_namespace="Another namespace",
    reopen_missing="Nothing was read back after reopening the connection; see the report.",
    reopen_answer="Written to SQLite, closed, and read back on a new connection: {value} (version {version}).",
    recall_only_title="Read-only recovery",
    recall_only_summary=(
        "Reads on a read-only connection: a real run reads the fixed teaching store, the offline test reads "
        "the sample seeded in a temporary store. No model was called."
    ),
    recall_only_check_writes="The reading connection changed no rows",
    recall_only_check_writes_detail="This connection's total_changes is {writes}.",
    recall_only_check_source="The record read carries its source",
    recall_only_check_source_detail="With no record, it honestly shows none.",
    label_lookup="Lookup result",
    value_found="found",
    row_read_only="Read-only read",
    recall_only_missing="Read-only recovery: there is no memory under this namespace and key.",
    recall_only_answer="Read-only recovery: {value} (source: {source}, version {version})",
    recall_title="Recall and put into the request",
    recall_summary=(
        "Memories are recalled on a read-only connection and put in the <memory> data block of the user message; "
        "system holds only rules. The keys in square brackets show what the answer relied on."
    ),
    recall_check_writes="The recall stage changed no rows",
    recall_check_writes_detail="total_changes is {writes}.",
    recall_check_placed="Memories are only in the data block of the user message; system has no memory content",
    recall_check_placed_detail="Checked against the messages actually sent; {count} recalled this time.",
    recall_check_grounded="Every key the answer cites is in this request's data block",
    recall_check_empty="With an empty data block, the answer cites no key",
    recall_cited_detail="Cited in the answer: {keys}",
    label_namespace="Namespace",
    label_recalled="Records recalled",
    recall_columns=("key", "Value", "Source", "Version", "Cited in the answer"),
    recall_empty_row="(no memories in this namespace)",
)
