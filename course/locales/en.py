"""Platform runtime text: English."""
from course.locales import Texts

TEXTS = Texts(
    tool_arguments_not_object="Tool arguments must be a JSON object.",
    unknown_tool="Unknown tool: {name}",
    rounds_exceeded="Stopped after {rounds} rounds of tool calls to avoid an endless loop.",
    run_cancelled="Stopped the remaining steps.",
    model_budget_exceeded="This lesson made more than {limit} model calls; no further calls were sent.",
    stage_result_title="Native sub-run result",
    bailian_http_error=(
        "Bailian returned HTTP {status}. The request was not resent automatically. Check your configuration "
        "and balance, and retry by hand once you know the cause, so you are not billed twice.\n{detail}"
    ),
    bailian_unreachable=(
        "Could not connect to Bailian; the request was not resent automatically. "
        "Check the network and the service status, then retry by hand.\n{reason}"
    ),
    provider_not_configured="Configure the model and service address of the selected provider first.",
    provider_key_missing="Configure the API key of the selected provider first.",
    embedding_not_configured=(
        "The selected provider has no embedding model configured. This lesson sends embedding requests and "
        "the platform will not switch to another model; set an embedding model in the model settings, or set "
        "the environment variable the documentation names, then run again."
    ),
    embedding_response_invalid=(
        "The embedding response has {actual} vectors for {expected} inputs; stopped."
    ),
    stream_interrupted=(
        "The streamed response broke off; the chunks received so far are on record. "
        "The request was not resent automatically.\n{reason}"
    ),
    stream_provider_error="The provider sent an error inside the streamed response; the chunks received so far are on record: {detail}",
    cli_model="Model: {model}",
    cli_examples="Try:",
    cli_prompt="\nYou: ",
    cli_no_question="No question received. Exiting.",
    cli_checking_key="\nChecking the process environment variable DASHSCOPE_API_KEY...",
    cli_key_not_in_env=(
        "This Python process did not find DASHSCOPE_API_KEY. "
        "You can enter the API key in the hidden prompt that follows."
    ),
    cli_key_prompt="API key for the region of your local Bailian configuration (input is hidden): ",
    cli_key_from_env="Read the API key from the process environment (its value is not shown).",
    cli_no_key="No API key provided. Exiting.",
    cli_key_ready="Key ready. Request logs never include the authentication key.",
    cli_request_body="\nRound {round}: full HTTP request body (authentication headers not included)",
    cli_waiting="Waiting for the response; the network timeout is 60 seconds...",
    cli_tool_request="\nThe model requests a tool: {name}({arguments})",
    cli_tool_result="Python result: {result}",
    cli_answer="\nAgent answer:\n{answer}",
    cli_failed="\nRun failed: {error}",
)
