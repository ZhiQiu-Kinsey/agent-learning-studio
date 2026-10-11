"""The smallest agent loop and tool dispatch: the tool-call lessons read this code.

The loop does four things: build the message history, send a request, decide
whether the run is over, and execute call proposals, writing each tool result back.
Recording events, timing and stop checks live in the complete / execute functions
the caller passes in: web runs get them from RunContext in course/execution.py,
command-line runs from run_cli below.
"""

import getpass
import json
import os
import sys
from dataclasses import dataclass

from course.api_client import send_bailian
from course.i18n import SOURCE_LOCALE
from course.locales import texts_for


@dataclass(frozen=True)
class AgentSetup:
    """What a native lesson sends in one run: the system prompt, tool definitions and the allowlist."""
    system_prompt: str
    tools: list
    available_tools: dict


def execute_tool(tool_call, available_tools, locale=SOURCE_LOCALE):
    """Execute one call proposal; on failure return a structured error to the model instead of crashing."""
    name = tool_call["function"]["name"]
    texts = texts_for(locale)
    try:
        # arguments is a JSON string written by the model: parse it and make sure it is an object.
        # A missing or empty string means no arguments.
        arguments = json.loads(tool_call["function"].get("arguments") or "{}")
        if not isinstance(arguments, dict):
            raise ValueError(texts.tool_arguments_not_object)
        # Allowlist: look the function up by name in available_tools only; an invented name never runs.
        function = available_tools.get(name)
        if function is None:
            raise ValueError(texts.unknown_tool.format(name=name))
        return {"ok": True, "result": function(**arguments)}
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        # A missing or extra argument raises TypeError at function(**arguments); it becomes a result too.
        return {"ok": False, "error_type": type(error).__name__, "error": str(error)}


def run_agent(question, system_prompt, tools, available_tools, max_tool_rounds, *, complete, execute=execute_tool,
              locale=SOURCE_LOCALE):
    """Run the tool-call loop until the model answers or the round limit is used up.

    complete(body, round_number): send the request body to the model, return the response.
    execute(tool_call, available_tools): execute one call proposal, return the tool result.
    """
    # 1. The message history starts with the system prompt and the user question.
    #    The model keeps nothing between rounds; each round it sees only this list.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    for round_number in range(1, max_tool_rounds + 1):
        # 2. Every round sends the whole history together with the tool definitions.
        response = complete({"messages": messages, "tools": tools, "tool_choice": "auto"}, round_number)
        message = response["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        # 3. No call proposals: content is the final answer.
        if not tool_calls:
            return message.get("content") or ""
        # 4. Put the assistant message with the proposals back into the history, then execute
        #    each one. Every tool result carries the same call id, so next round the model
        #    can match results to calls.
        messages.append(message)
        for tool_call in tool_calls:
            result = execute(tool_call, available_tools)
            messages.append({"role": "tool", "tool_call_id": tool_call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    # Out of rounds without an answer: stop with an error instead of returning half a result.
    raise RuntimeError(
        texts_for(locale).rounds_exceeded.format(rounds=max_tool_rounds))


class RunCancelled(RuntimeError):
    """Stop the remaining steps; an HTTP request already sent is still bound by the network timeout."""


def run_cli(setup, *, title, examples, max_tool_rounds, locale=SOURCE_LOCALE):
    """Command-line entry: read the question and key, print each request body and tool result, run the same loop."""
    from local_config import MODEL

    texts = texts_for(locale)
    print(title)
    print(texts.cli_model.format(model=MODEL))
    print(texts.cli_examples)
    for example in examples:
        print("  - {}".format(example))

    question = input(texts.cli_prompt).strip()
    if not question:
        print(texts.cli_no_question)
        return

    print(texts.cli_checking_key, flush=True)
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print(texts.cli_key_not_in_env, flush=True)
        api_key = getpass.getpass(texts.cli_key_prompt).strip()
    else:
        print(texts.cli_key_from_env, flush=True)

    if not api_key:
        print(texts.cli_no_key)
        return

    print(texts.cli_key_ready, flush=True)

    def complete(body, round_number):
        request = {"model": MODEL, **body}
        print(texts.cli_request_body.format(round=round_number), flush=True)
        print(json.dumps(request, ensure_ascii=False, indent=2), flush=True)
        print(texts.cli_waiting, flush=True)
        return send_bailian(request, api_key, locale=locale)

    def execute(tool_call, tools_by_name):
        print(texts.cli_tool_request.format(name=tool_call["function"]["name"],
                                            arguments=tool_call["function"].get("arguments")))
        result = execute_tool(tool_call, tools_by_name, locale)
        print(texts.cli_tool_result.format(result=json.dumps(result, ensure_ascii=False)))
        return result

    try:
        answer = run_agent(question, setup.system_prompt, setup.tools, setup.available_tools, max_tool_rounds,
                           complete=complete, execute=execute, locale=locale)
        print(texts.cli_answer.format(answer=answer))
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
        print(texts.cli_failed.format(error=error), file=sys.stderr)
