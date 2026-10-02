"""把各服务商响应里的缓存字段归一成同一种形状。

字段名以各服务商文档为准（2026-10-03 核对）；归一化只读响应里实际出现的字段，不按长度估算。
"""

EMPTY = {"input_tokens": None, "cached_tokens": None, "cache_write_tokens": None, "field": None}


def _count(value) -> int | None:
    # bool 是 int 的子类，True 不能当成 1 个 Token；小数、字符串、负数都不猜测换算。
    return value if type(value) is int and value >= 0 else None


def normalize_cache_usage(usage) -> dict:
    """返回 input_tokens（全部输入，含命中）、cached_tokens（命中）、cache_write_tokens（写入缓存）
    和 field（命中数取自哪个字段）。cached_tokens 为 None 表示没有报告，和“报告为 0”是两回事。
    """
    if not isinstance(usage, dict):
        return dict(EMPTY)
    write = _count(usage.get("cache_creation_input_tokens"))
    details = usage.get("prompt_tokens_details")
    # 1. OpenAI 兼容接口（百炼也是）：命中数包含在 prompt_tokens 里。
    if isinstance(details, dict) and _count(details.get("cached_tokens")) is not None:
        return {"input_tokens": _count(usage.get("prompt_tokens")), "cached_tokens": details["cached_tokens"],
                "cache_write_tokens": write, "field": "prompt_tokens_details.cached_tokens"}
    # 2. DeepSeek 官方接口：命中与未命中分成两个字段，合起来是全部输入。
    hit = _count(usage.get("prompt_cache_hit_tokens"))
    if hit is not None:
        total = _count(usage.get("prompt_tokens"))
        miss = _count(usage.get("prompt_cache_miss_tokens"))
        if total is None and miss is not None:
            total = hit + miss
        return {"input_tokens": total, "cached_tokens": hit, "cache_write_tokens": write,
                "field": "prompt_cache_hit_tokens"}
    # 3. Anthropic：input_tokens 不含缓存读写，三项相加才是全部输入。
    base = _count(usage.get("input_tokens"))
    read = _count(usage.get("cache_read_input_tokens"))
    if read is not None:
        total = None if base is None else base + read + (write or 0)
        return {"input_tokens": total, "cached_tokens": read, "cache_write_tokens": write,
                "field": "cache_read_input_tokens"}
    # 4. 没有任何缓存字段：命中数未报告，输入总数照常读取。
    total = _count(usage.get("prompt_tokens"))
    if total is None and base is not None:
        total = base + (write or 0)
    return {**EMPTY, "input_tokens": total, "cache_write_tokens": write}


def hit_ratio(cache: dict) -> float | None:
    """命中 ÷ 全部输入；命中未报告、输入未知或为 0 时没有比例。"""
    cached, total = cache["cached_tokens"], cache["input_tokens"]
    if cached is None or not total:
        return None
    return round(cached / total, 4)
