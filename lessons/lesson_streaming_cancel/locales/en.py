"""Runtime text: English."""
from lessons.lesson_streaming_cancel.locales import Texts

TEXTS = Texts(
    system=("You are the explainer of a course. Answer in exactly the format the user asks for, with no opening "
            "remarks and no summary."),
    task=("Explain, in a numbered list of {items} items, what the program and the model each do in one round of an "
          "Agent loop. {length} per item, in the form \"1. ...\", each item on its own line, nothing outside the list."),
    lengths={"short": "One sentence", "long": "Three sentences"},
    continue_plain="Continue",
    continue_marked=(
        "[The previous answer was not finished] The program stopped it after {chunks} chunks, before the model gave "
        "a finish reason, so what follows is only the part that was written in full, not a complete answer.\n"
        "The first {kept_count} items, written in full:\n{kept}\n"
        "Write only item {next_item} to item {items}, in the same format. Do not repeat the items already written "
        "and write nothing else."
    ),
    continue_marked_none=(
        "[The previous answer was not finished] The program stopped it after {chunks} chunks, before a single item "
        "was written in full. Write item {next_item} to item {items}, in the same format, and nothing else."
    ),
    marked_phrase="was not finished",
    value_empty="(empty)",
    value_none="none",
    flag_yes="yes",
    flag_no="no",
    not_reported="not reported",
    not_received="not received",
    no_finish_marker="none (the model had not finished)",
    usage_line="input {prompt}, output {completion}, total {total} (tokens)",
    statuses={"completed": "ended normally (completed)", "stopped": "stopped by the program (stopped)",
              "cancelled": "run stopped (cancelled)", "error": "error (error)"},
    report_titles={"compare": "Streamed and not streamed, side by side", "long": "Receiving a long answer as a stream",
                   "stop": "The program stops after chunk N", "continue": "The next round after an incomplete answer"},
    report_summaries={
        "compare": ("The same request is sent twice, streamed and then not streamed. The times come from this "
                    "process's clock, one sample each in a fixed order; they do not describe the provider's latency."),
        "long": ("One long answer received as a stream. While it runs you can press \"Stop run\" or \"Disconnect the event "
                 "stream\"; this report exists only when the stream ends normally."),
        "stop": ("The program ended the stream after the set number of chunks. The run goes on and what it holds is a "
                 "partial result: no finish reason, and the provider sent no usage chunk."),
        "continue": ("One cut piece of text is handed back to the model in two ways: as it is, glued on like a finished "
                     "message, or marked incomplete with only the missing part requested. One request each, in a "
                     "fixed order."),
    },
    label_status="How the stream ended",
    label_chunks="Chunks",
    label_first_chunk="First chunk arrived (ms)",
    label_first_token="Time to first token (ms)",
    label_stream_ms="Streamed total (ms)",
    label_chars="Characters of text",
    label_finish="Finish reason (finish_reason)",
    label_usage="Usage",
    label_plain_ms="Not streamed total (ms)",
    label_only_plain="Top-level fields only in the not streamed response",
    label_only_streamed="Top-level fields only in the assembled response",
    label_note="Learner note",
    label_stop_after="Stop point (chunks)",
    label_items_seen="Numbered items received",
    label_kept="Items written in full",
    label_next_item="First item to continue",
    label_cut_line="The line cut in the middle",
    check_completed="The stream ended normally and a finish reason arrived",
    detail_completed="Ended as {status}, finish reason {reason}",
    check_first_before_total="The first token arrived before the total time",
    detail_first_before_total="First token {first} ms, streamed total {total} ms",
    check_shape="The assembled response and the not streamed response have the same message shape",
    detail_shape_ok="Both first messages have a role, text content, and a finish_reason that is text",
    detail_shape_bad="Different shape: streamed {streamed}, not streamed {plain}",
    check_list="The numbered list is whole",
    detail_list="Expected 1 to {expected}, every line finished; actual numbers {numbers}",
    check_stop_reached="The program ended the stream at the stop point",
    detail_stop_reached="Stop point {limit} chunks, received {chunks}, ended as {status}",
    check_finish_missing="No finish reason arrived, so the missing end is visible in the data",
    detail_finish_missing="Finish reason: {reason}",
    check_marked_request="The marked request says \"was not finished\" and names the item to continue from",
    detail_marked_request="Continues from item {next_item}",
    check_plain_merge="The list is whole after gluing the reply on as it is",
    check_marked_merge="The list is whole after the marked merge",
    detail_merge="Merged numbers {numbers}; {verdict}",
    verdict_ok="numbers run from 1 to the last item, each once, every line finished, and the continuation request ended normally",
    verdict_bad=("did not pass: repeated numbers {duplicates}, missing numbers {missing}, unfinished lines {unfinished}; "
                 "or the continuation request did not end normally"),
    compare_columns=("Item", "Streamed (assembled)", "Not streamed"),
    row_first_chunk="First chunk arrived (ms)",
    row_first_token="First token arrived (ms)",
    row_total="Total time (ms)",
    row_finish="Finish reason",
    row_usage="Usage",
    row_chars="Characters of text",
    row_items="Numbered items",
    continue_columns=("Handling", "Request says incomplete", "Continuation finish reason", "Merged numbers",
                      "Repeated numbers", "Missing numbers", "Unfinished lines"),
    handling_plain="Glued on as it is",
    handling_marked="Marked incomplete",
    answers={
        "compare": ("Streamed: the first token arrived at {first} ms, the total was {total} ms, {chunks} chunks; not "
                    "streamed: the total was {plain} ms. These are one sample each from this run."),
        "long": ("The stream ended normally: {chunks} chunks, {chars} characters, first token at {first} ms, total "
                 "{total} ms."),
        "stop": ("The program stopped receiving after {chunks} chunks (stop point {limit}). Below are the {chars} "
                 "characters that arrived. This is a partial result, not a complete answer:\n\n{text}"),
        "stop_not_reached": ("The stream ended before the stop point {limit}, after {chunks} chunks; the program did "
                             "not stop it early, so there is no partial result this time."),
        "continue_not_reached": ("The stream ended before the stop point {limit}, after {chunks} chunks. Nothing was "
                                 "cut off, so there is nothing to continue from."),
        "continue_no_text": ("No text had arrived by the stop point {limit} (the model may still be writing its reasoning), "
                             "so there is nothing to continue from; raise the stop point and try again."),
        "continue_nothing_missing": ("The list was already written when the stream was stopped, so no item is missing "
                                     "and nothing needs continuing (stop point {limit}, {chunks} chunks received)."),
        "continue_ok": "The marked merge passed the check; the list of {items} items:\n\n{text}",
        "continue_bad": ("The marked merge did not pass the check and is not offered as a complete answer; the report "
                         "shows the result of both handlings."),
    },
)
