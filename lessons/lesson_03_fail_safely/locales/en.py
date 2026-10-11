"""fail-safely runtime text: English."""
from lessons.lesson_03_fail_safely.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "You are a teaching calculator assistant. When the user asks for a division, call divide_numbers. "
        "If the tool returns ok=false, state the error truthfully and ask the user to fix the input; "
        "do not make up a quotient, and do not repeat the same invalid request. "
        "Report a result only after the tool returns ok=true."
    ),
    divide_numbers=(
        "Divide a by b and return quotient. Both arguments must be finite numbers; "
        "b cannot be 0. Call it when the user asks for a division."
    ),
    divide_numbers_a="The dividend",
    divide_numbers_b="The divisor; cannot be 0",
    not_a_number="Argument {name} must be a number.",
    not_finite="Both arguments must be finite numbers within the supported range.",
    zero_divisor="The divisor cannot be 0; please provide a non-zero divisor.",
    out_of_range="The result is outside the supported range.",
    fault_answer=(
        "No model was called in this arm. The call the runner built, {name} (arguments {arguments}), "
        "was rejected before execution: {error_type}: {error}. No tool function was executed."
    ),
    cli_title="Error handling and safety boundaries",
    cli_examples=("What is 12 divided by 3?", "What is 12 divided by 0? Explain how it was handled."),
    demo_intro="Offline error-handling demo: no Bailian call, no API key needed.",
    demo_result="Tool result returned to the model: {result}",
    demo_cases={
        "valid": "Valid arguments",
        "zero": "Zero divisor",
        "unknown": "The model asked for an unregistered tool",
        "malformed": "The tool arguments are not valid JSON",
    },
)
