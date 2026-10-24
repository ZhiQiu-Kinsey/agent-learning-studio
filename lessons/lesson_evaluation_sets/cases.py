"""The versioned evaluation suite: what each case expects, written before any version is run.

The specs are language-neutral code. The question of each case is runtime text, keyed by
case id in locales/, so a Chinese and an English run ask the same thing in their own
language and are judged by the same spec.
"""
import hashlib
import json
from dataclasses import asdict, dataclass, field

# Bump the suite version whenever a case is added, removed or its expectation changes;
# a score is only comparable with scores of the same suite version.
SUITE_VERSION = "tools-suite-v1"
# Model calls one case may use. The agent under test stops (instead of raising) when it
# runs out, so the verifier can record "the run did not end" as a result.
CASE_ROUNDS = 3


@dataclass(frozen=True)
class Case:
    id: str
    split: str  # "dev": used while changing the agent; "holdout": run once a version is chosen
    category: str  # simple, dependent, failure, no_tool, parallel, missing_evidence
    # Expected calls as (tool name, arguments). An argument {"ref": "tool.field"} must come
    # from that field of the tool's first successful result in the same run.
    calls: tuple = ()
    # sequence: same calls in the same order; unordered: same calls, any order; none: no call.
    mode: str = "sequence"
    # {"values": [...]}: these numbers; {"compute": [op, x, y]}: the verifier computes the
    # number itself from recorded tool results; {"none": True}: must answer NONE;
    # {"open": True}: free text a program cannot judge.
    answer: dict = field(default_factory=dict)
    rev: int = 1  # case revision: bump it when this case changes


def _ref(path: str) -> dict:
    return {"ref": path}


CASES = (
    Case("add-basic", "dev", "simple", (("add_numbers", {"a": 19, "b": 23}),), answer={"values": [42]}),
    Case("clock-sum", "dev", "dependent",
         (("get_current_time", {}),
          ("add_numbers", {"a": _ref("get_current_time.hour"), "b": _ref("get_current_time.minute")})),
         answer={"compute": ["add", "get_current_time.hour", "get_current_time.minute"]}),
    Case("divide-zero", "dev", "failure", (("divide_numbers", {"a": 100, "b": 0}),), answer={"none": True}),
    Case("greeting", "dev", "no_tool", mode="none", answer={"open": True}),
    Case("two-sums", "dev", "parallel",
         (("add_numbers", {"a": 19, "b": 23}), ("add_numbers", {"a": 100, "b": 5})),
         mode="unordered", answer={"values": [42, 105]}),
    Case("unknown-balance", "dev", "missing_evidence", mode="none", answer={"none": True}),
    Case("add-holdout", "holdout", "simple", (("add_numbers", {"a": 58, "b": 67}),), answer={"values": [125]}),
    Case("divide-zero-holdout", "holdout", "failure", (("divide_numbers", {"a": 7, "b": 0}),),
         answer={"none": True}),
    Case("given-distance", "holdout", "no_tool", mode="none", answer={"values": [12]}),
    Case("clock-half", "holdout", "dependent",
         (("get_current_time", {}), ("divide_numbers", {"a": _ref("get_current_time.hour"), "b": 2})),
         answer={"compute": ["divide", "get_current_time.hour", 2]}),
)

# Tools whose two arguments may be swapped without changing the result: a structured
# comparison has to decide up front which differences are not errors.
COMMUTATIVE = {"add_numbers"}

# Calibration samples for the open-ended "greeting" case: fixed answers written by the
# lesson author, each with the author's human label. They are evaluation data, not runs.
JUDGE_SAMPLES = (
    ("j1", "pass"),
    ("j2", "fail"),
    ("j3", "fail"),
    ("j4", "pass"),
    ("j5", "pass"),
    ("j6", "fail"),
)


def cases_for(split: str) -> list[Case]:
    return [case for case in CASES if case.split == split]


def fingerprint(cases: list[Case]) -> str:
    """A short hash of the specs: if a case changes silently, the fingerprint in the report changes too."""
    text = json.dumps([asdict(case) for case in cases], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
