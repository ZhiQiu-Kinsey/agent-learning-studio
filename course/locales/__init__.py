"""Platform runtime text: messages that course/ sends to the model, into events or to the terminal.

One field per message. Templates use named ``str.format`` fields; every locale's
catalog must use the same fields (tests/test_runtime_locales.py checks it).
Messages for developers (programming errors) are plain English in the code instead.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Structured tool errors returned to the model (course/runner.py execute_tool).
    tool_arguments_not_object: str
    unknown_tool: str  # {name}
    # The native loop ran out of rounds (course/runner.py run_agent).
    rounds_exceeded: str  # {rounds}
    # RunContext (course/execution.py).
    run_cancelled: str
    model_budget_exceeded: str  # {limit}
    stage_result_title: str
    # Model connections (course/api_client.py, course/providers.py).
    bailian_http_error: str  # {status}, {detail}
    bailian_unreachable: str  # {reason}
    provider_not_configured: str
    provider_key_missing: str
    # Embedding requests (RunContext.embed): no embedding model for the provider, or a response
    # whose vectors do not match the inputs.
    embedding_not_configured: str
    embedding_response_invalid: str  # {expected}, {actual}
    # Streaming requests (RunContext.complete_stream): the stream broke off, or the provider sent an
    # error object inside it. The chunks received before that are already on record.
    stream_interrupted: str  # {reason}
    stream_provider_error: str  # {detail}
    # Command-line runs (course/runner.py run_cli).
    cli_model: str  # {model}
    cli_examples: str
    cli_prompt: str
    cli_no_question: str
    cli_checking_key: str
    cli_key_not_in_env: str
    cli_key_prompt: str
    cli_key_from_env: str
    cli_no_key: str
    cli_key_ready: str
    cli_request_body: str  # {round}
    cli_waiting: str
    cli_tool_request: str  # {name}, {arguments}
    cli_tool_result: str  # {result}
    cli_answer: str  # {answer}
    cli_failed: str  # {error}


texts_for = catalog(__name__, Texts)
