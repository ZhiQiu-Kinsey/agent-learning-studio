"""Offline test vectors for embedding-retrieval: serve automated tests only and stand for no real embedding model.

Each vector is built by hand from the concept vocabulary in test_vectors.json: one dimension per
concept, counting how often its words appear, plus one constant dimension every text shares (so no
vector is all zeros). Synonyms such as late fee / overdue charge share a dimension, while codes
such as B2 or R-305 have none. That reproduces, by construction, what the lesson discusses: a
paraphrased query finds its section, a query that hinges on a code does not. Whether a real model
behaves this way can only be checked with a live run.

Vectors are padded with zeros to the requested `dimensions`; zeros change no cosine, so offline
results are the same at every size. The usage numbers are scripted (one per input character).
"""
import json
import re
from functools import lru_cache
from pathlib import Path

VOCABULARY = Path(__file__).resolve().parent / "test_vectors.json"
DEFAULT_SIZE = 64  # used when a request names no dimensions


@lru_cache(maxsize=None)
def _matcher(locale: str):
    concepts = json.loads(VOCABULARY.read_text(encoding="utf-8"))["concepts"]
    owner = {form.lower(): index for index, concept in enumerate(concepts) for form in concept[locale]}
    # Longest form first, so a longer phrase is counted once instead of also counting its parts.
    forms = sorted(owner, key=len, reverse=True)
    if locale == "en":
        # Whole words only, allowing a plural or verb ending: "books" counts as "book", "bookshelf" does not.
        pattern = r"(?<![a-z0-9])(" + "|".join(map(re.escape, forms)) + r")(?:s|es|ed|ing)?(?![a-z0-9])"
    else:
        pattern = "(" + "|".join(map(re.escape, forms)) + ")"
    return re.compile(pattern), owner, len(concepts)


def concept_vector(text: str, locale: str, size: int = DEFAULT_SIZE) -> list[float]:
    regex, owner, count = _matcher(locale)
    if size < count + 1:
        raise ValueError(f"test vectors need at least {count + 1} dimensions")
    values = [0.0] * size
    values[count] = 1.0  # the shared dimension
    for match in regex.finditer(text.lower()):
        values[owner[match.group(1)]] += 1.0
    return values


def create_embedding(exercise_id, inputs=None, locale="zh-CN"):
    def embedding(body, api_key):
        size = body.get("dimensions") or DEFAULT_SIZE
        texts = body["input"]
        return {"object": "list", "model": body["model"],
                "data": [{"object": "embedding", "index": index, "embedding": concept_vector(text, locale, size)}
                         for index, text in enumerate(texts)],
                "usage": {"prompt_tokens": sum(map(len, texts)), "total_tokens": sum(map(len, texts))}}

    return embedding
