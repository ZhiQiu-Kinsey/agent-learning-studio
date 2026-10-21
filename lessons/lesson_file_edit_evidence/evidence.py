"""Change evidence that does not depend on what the model says: diffs for one edit, which parts of a Python file
changed, the unittest summary line, and a check that the journal fits the files.

A journal row is written next to each write-type tool call (file_tools.py). This module turns two versions of a
file into a unified diff, and replays the journal against the workspace's own before/after hashes: if a row is
missing, invented or out of order, the chain of hashes breaks and the check says where.
"""
import ast
import difflib
import re

DIFF_LIMIT = 1600


def unified_diff(path: str, before: str | None, after: str | None, *, limit: int = DIFF_LIMIT) -> tuple[str, int, int]:
    """Unified diff of one file as (text, added lines, removed lines); None means the file does not exist on that side.

    The text is cut in the middle past ``limit``: the headers and the first hunk are what a reader needs,
    and the counts stay exact because they are taken before cutting.
    """
    old_lines = (before or "").splitlines(keepends=True)
    new_lines = (after or "").splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        old_lines, new_lines, fromfile="/dev/null" if before is None else f"a/{path}",
        tofile="/dev/null" if after is None else f"b/{path}", n=2))
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    text = "".join(line if line.endswith("\n") else line + "\n" for line in diff)
    if len(text) > limit:
        half = limit // 2
        text = text[:half] + f"[... {len(text) - 2 * half} chars omitted ...]\n" + text[-half:]
    return text, added, removed


def verify_chain(journal: list[dict], baseline: dict[str, str], final: dict[str, str]) -> list[dict]:
    """Replay the journal and compare it with the workspace's own snapshots; return the problems found.

    For every file: the first changing row must start from the baseline hash, each row must start where the
    previous one ended, and the last row must end at the hash the file has now. A file that differs from the
    baseline without any row is an unexplained change. Rejected rows change nothing and are skipped.
    """
    problems: list[dict] = []
    current = dict(baseline)
    touched: set[str] = set()
    for row in journal:
        if not row.get("ok") or not row.get("changed"):
            continue
        path = row["path"]
        touched.add(path)
        if row["before_sha256"] != current.get(path):
            problems.append({"path": path, "seq": row["seq"], "reason": "broken_chain"})
        current[path] = row["after_sha256"]
    for path in sorted(set(current) | set(final)):
        if current.get(path) != final.get(path):
            problems.append({"path": path, "seq": None,
                             "reason": "unexplained_change" if path not in touched else "final_mismatch"})
    return problems


def _symbols(source: str) -> dict[str, str] | None:
    """Top-level names of a Python file mapped to their source text; None when the file does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    symbols: dict[str, str] = {}
    for index, node in enumerate(tree.body):
        segment = ast.get_source_segment(source, node) or ""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [segment]
        elif index == 0 and isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) \
                and isinstance(node.value.value, str):
            names = ["<docstring>"]
        else:
            names = []
        for name in names:
            symbols[name] = segment
    return symbols


def symbol_changes(before: str, after: str) -> dict[str, list[str]] | None:
    """Which top-level functions, classes, assignments and imports differ between two versions of a file.

    A whole-file rewrite that silently drops a function shows up here as ``removed`` even when the model never
    mentions it. None when either version does not parse: the caller must say so, not guess.
    """
    old, new = _symbols(before), _symbols(after)
    if old is None or new is None:
        return None
    return {"changed": sorted(name for name in old.keys() & new.keys() if old[name] != new[name]),
            "added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys())}


def unittest_summary(output: str) -> dict:
    """The facts on unittest's closing lines: how many tests ran and the verdict word with its counts."""
    ran = re.search(r"^Ran (\d+) tests? in", output, re.MULTILINE)
    verdicts = re.findall(r"^(OK|FAILED|NO TESTS RAN)\b(.*)$", output, re.MULTILINE)
    return {"ran": int(ran.group(1)) if ran else None,
            "outcome": verdicts[-1][0] if verdicts else None,
            "detail": verdicts[-1][1].strip(" ()") if verdicts else ""}
