"""Normalize the cache fields of different providers' responses into one shape.

Field names follow each provider's documentation (checked 2026-10-03); only fields that actually appear are read,
nothing is estimated from length.
"""

EMPTY = {"input_tokens": None, "cached_tokens": None, "cache_write_tokens": None, "field": None}


def _count(value) -> int | None:
    # bool is a subclass of int, and True is not 1 token; floats, strings and negatives are not converted by guessing.
    return value if type(value) is int and value >= 0 else None


def normalize_cache_usage(usage) -> dict:
    """Return input_tokens (all input, hits included), cached_tokens (hits), cache_write_tokens (written to cache)
    and field (where the hit count came from). cached_tokens None means not reported, which differs from "reported 0".
    """
    if not isinstance(usage, dict):
        return dict(EMPTY)
    write = _count(usage.get("cache_creation_input_tokens"))
    details = usage.get("prompt_tokens_details")
    # 1. OpenAI-compatible endpoints (Bailian too): the hits are part of prompt_tokens.
    if isinstance(details, dict) and _count(details.get("cached_tokens")) is not None:
        return {"input_tokens": _count(usage.get("prompt_tokens")), "cached_tokens": details["cached_tokens"],
                "cache_write_tokens": write, "field": "prompt_tokens_details.cached_tokens"}
    # 2. DeepSeek's own API: hits and misses are two fields that add up to all input.
    hit = _count(usage.get("prompt_cache_hit_tokens"))
    if hit is not None:
        total = _count(usage.get("prompt_tokens"))
        miss = _count(usage.get("prompt_cache_miss_tokens"))
        if total is None and miss is not None:
            total = hit + miss
        return {"input_tokens": total, "cached_tokens": hit, "cache_write_tokens": write,
                "field": "prompt_cache_hit_tokens"}
    # 3. Anthropic: input_tokens excludes cache reads and writes; all input is the sum of the three.
    base = _count(usage.get("input_tokens"))
    read = _count(usage.get("cache_read_input_tokens"))
    if read is not None:
        total = None if base is None else base + read + (write or 0)
        return {"input_tokens": total, "cached_tokens": read, "cache_write_tokens": write,
                "field": "cache_read_input_tokens"}
    # 4. No cache field at all: hits are not reported, the input total is read as usual.
    total = _count(usage.get("prompt_tokens"))
    if total is None and base is not None:
        total = base + (write or 0)
    return {**EMPTY, "input_tokens": total, "cache_write_tokens": write}


def hit_ratio(cache: dict) -> float | None:
    """Hits / all input; no ratio when hits are not reported or the input is unknown or 0."""
    cached, total = cache["cached_tokens"], cache["input_tokens"]
    if cached is None or not total:
        return None
    return round(cached / total, 4)
