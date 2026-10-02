"""提示缓存课的离线测试模型：只服务自动化测试，不代表任何服务商的行为。

夹具记住本次运行里发过的请求，按“和之前某次请求从头相同的字符数”编造命中数：每 2 个字符算 1 个 Token，
按 64 个 Token 一档向下取整。前缀不同就报告 0；“稳定前缀 + 预热”组故意不返回任何缓存字段，用来测试“未报告”。
"""
import json
import os

# 每组练习用哪种用量格式；测试可以用 style 参数换成其他服务商的写法。
STYLES = {"dynamic-first": "openai", "stable-prefix": "openai", "warmup": "none"}
BLOCK = 64


def _tokens(text: str) -> int:
    return len(text) // 2


def _shared(text: str, earlier: list[str]) -> int:
    """和之前任何一次请求从头相同的最长字符数。"""
    return max((len(os.path.commonprefix([text, other])) for other in earlier), default=0)


def usage_in_style(style: str, total: int, cached: int, output: int) -> dict:
    """同一组数字，按不同服务商的字段写法返回。"""
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
    raise ValueError(f"未知用量格式：{style}")


def create_completion(exercise_id, inputs=None, style=None):
    if style is None:
        if exercise_id not in STYLES:
            raise ValueError("未知的提示缓存练习。")
        style = STYLES[exercise_id]
    earlier: list[str] = []

    def complete(body, api_key):
        text = json.dumps(body["messages"], ensure_ascii=False)
        cached = _shared(text, earlier) // 2 // BLOCK * BLOCK
        earlier.append(text)
        question = body["messages"][-1]["content"].split("\n")[0]
        answer = f"（离线夹具）收到问题：{question}"
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": usage_in_style(style, _tokens(text), cached, _tokens(answer))}

    return complete
