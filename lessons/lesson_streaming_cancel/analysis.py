"""Pure checks on streamed text: numbered items, where a cut landed, how two pieces merge, response shapes.

Nothing here calls the model or records events. The lesson asks for a numbered list on purpose: whether a list
is whole is something Python can check (numbers 1..N, each once, every line finished), so a partial answer is
judged by the data and not by how fluent it sounds. The check cannot see garbled text inside one line.
"""
import re
from dataclasses import dataclass

# One item starts a line: "3. text" (a full-width dot or a closing parenthesis also count).
ITEM = re.compile(r"^[ \t]*(\d{1,2})[.\u3001)\uff09][ \t]*(\S.*)$", re.MULTILINE)
# Full-width marks are spelled as code points so that no Chinese text sits in this file.
SENTENCE_END = (".", "!", "?", chr(0x3002), chr(0xFF01), chr(0xFF1F))


def parse_items(text: str) -> list[tuple[int, str]]:
    """(number, line text) for every numbered line, in the order they appear."""
    return [(int(match.group(1)), match.group(2).strip()) for match in ITEM.finditer(text)]


def clean_end(text: str) -> bool:
    """Whether the text stops at a sentence end. A cut in the middle of a sentence does not."""
    return text.rstrip().endswith(SENTENCE_END)


@dataclass(frozen=True)
class Partial:
    """What an incomplete answer still holds: the part that can be trusted and where the rest must start."""
    text: str
    kept: str  # lines that were written out in full
    kept_count: int
    next_item: int  # the first item number that still has to be written
    cut_line: str | None  # the half-written last line, None when the text stops at a sentence end


def analyse_partial(text: str) -> Partial:
    items = parse_items(text)
    if not items:
        return Partial(text, "", 0, 1, text.strip() or None)
    last_number = items[-1][0]
    if clean_end(text):
        # One sentence per item here, so a sentence end is also an item end.
        return Partial(text, text.rstrip(), len(items), last_number + 1, None)
    # The last line was cut off: keep everything before it and ask for that item again from its start.
    last_start = list(ITEM.finditer(text))[-1].start()
    return Partial(text, text[:last_start].rstrip(), len(items) - 1, last_number, text[last_start:].strip())


def merge_plain(partial_text: str, continuation: str) -> str:
    """What an app does that treats the cut text as a finished message: glue the new text on as it comes."""
    return partial_text + continuation


def merge_marked(partial: Partial, continuation: str) -> str:
    """Keep only the lines that were written in full, then the new lines."""
    head = partial.kept + "\n" if partial.kept else ""
    return head + continuation.strip()


def numbering(text: str, expected: int) -> dict:
    """Is the list whole? Numbers exactly 1..expected, each once, and every line ends at a sentence end."""
    items = parse_items(text)
    numbers = [number for number, _ in items]
    unfinished = [number for number, line in items if not clean_end(line)]
    return {
        "numbers": numbers,
        "duplicates": sorted({number for number in numbers if numbers.count(number) > 1}),
        "missing": [number for number in range(1, expected + 1) if number not in numbers],
        "unfinished": unfinished,
        "whole": numbers == list(range(1, expected + 1)) and not unfinished,
    }


def message_of(response: dict) -> dict:
    choice = (response.get("choices") or [{}])[0]
    return choice.get("message") or {}


def finish_reason_of(response: dict):
    return (response.get("choices") or [{}])[0].get("finish_reason")


def shape_of(response: dict) -> dict:
    """The fields a caller reads from a chat completion, nothing provider specific."""
    message = message_of(response)
    reason = finish_reason_of(response)
    return {"role": message.get("role"), "content_is_text": isinstance(message.get("content"), str),
            "finish_reason_is_text": isinstance(reason, str)}


def only_in_one(streamed: dict, plain: dict) -> tuple[list[str], list[str]]:
    """Top-level fields that exist in one body but not in the other: (only streamed, only plain)."""
    return sorted(set(streamed) - set(plain)), sorted(set(plain) - set(streamed))
