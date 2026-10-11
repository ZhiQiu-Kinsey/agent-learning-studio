"""Offline test model for prompt-caching: serves automated tests only and stands for no provider.

The fixture remembers the requests of this run and makes up the hit count from "characters identical from the start
with an earlier request": 2 characters count as 1 token, rounded down to blocks of 64 tokens. A different prefix
reports 0; the "stable prefix + warmup" arm deliberately returns no cache field, to test "not reported".
"""
import json
import os

# The usage format each exercise uses; tests can switch to another provider's shape with the style parameter.
STYLES = {"dynamic-first": "openai", "stable-prefix": "openai", "warmup": "none"}
BLOCK = 64
ANSWERS = {"zh-CN": "（离线夹具）收到问题：{question}", "en": "(offline fixture) Question received: {question}"}


def _tokens(text: str) -> int:
    return len(text) // 2


def _shared(text: str, earlier: list[str]) -> int:
    """The longest run of identical characters from the start with any earlier request."""
    return max((len(os.path.commonprefix([text, other])) for other in earlier), default=0)


def usage_in_style(style: str, total: int, cached: int, output: int) -> dict:
    """The same numbers, in the field names of different providers."""
    if style == "openai":
        return {"prompt_tokens": total, "completion_tokens": output, "total_tokens": total + output,
                "prompt_tokens_details": {"cached_tokens": cached}}
    if style == "deepseek":
        return {"prompt_tokens": total, "completion_tokens": output, "total_tokens": total + output,
                "prompt_cache_hit_tokens": cached, "prompt_cache_miss_tokens": total - cached}
    if style == "anthropic":
        return {"input_tokens": total - cached, "output_tokens": output,
                "cache_read_input_tokens": cached, "cache_creation_input_tokens": 0}
    if style == "none":
        return {"prompt_tokens": total, "completion_tokens": output, "total_tokens": total + output}
    raise ValueError(f"unknown usage style: {style}")


def create_completion(exercise_id, inputs=None, locale="zh-CN", style=None):
    if style is None:
        if exercise_id not in STYLES:
            raise ValueError(f"prompt-caching has no offline exercise {exercise_id!r}")
        style = STYLES[exercise_id]
    earlier: list[str] = []

    def complete(body, api_key):
        text = json.dumps(body["messages"], ensure_ascii=False)
        cached = _shared(text, earlier) // 2 // BLOCK * BLOCK
        earlier.append(text)
        question = body["messages"][-1]["content"].split("\n")[0]
        answer = ANSWERS[locale].format(question=question)
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": usage_in_style(style, _tokens(text), cached, _tokens(answer))}

    return complete
