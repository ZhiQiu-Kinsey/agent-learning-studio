"""The file tools of file-edit-evidence: read_file, write_file, edit_file and edit_lines over one Workspace.

Every path goes through ``Workspace.resolve``. Every write-type call passes the same guards (protected path,
read before write, file unchanged since the read, tool-specific checks) and leaves one journal row with the
sha256 of the file before and after, a unified diff and the added and removed line counts. A rejected call
leaves a row too, with ok=false and an error_type, so the journal explains the refusals as well.

Failures are exceptions that subclass ValueError: execute_tool turns only ValueError and TypeError into a
structured tool result (ok=false, error_type, error); the class name is the error_type. The message is
looked up in the run's locale because the model reads it.
"""
import contextlib
import fnmatch
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from course.sandbox import Workspace, sha256_bytes
from lessons.lesson_file_edit_evidence.evidence import unified_diff

MAX_FILE_BYTES = 200_000
READ_LIMIT_LINES = 400
DEFAULT_PROTECTED = ("tests/*",)


class ToolFailure(ValueError):
    """Base of this lesson's tool errors; ValueError because execute_tool only converts ValueError and TypeError."""


class PathOutsideWorkspace(ToolFailure):
    """The path is empty, absolute, climbs out with .., starts with ~ or resolves outside the workspace."""


class ProtectedPath(ToolFailure):
    """A write to a file the task forbids changing (the tests)."""


class FileNotFound(ToolFailure):
    """The path does not exist."""


class NotATextFile(ToolFailure):
    """A directory, a binary file, a file that is not UTF-8, or one past the size limit."""


class NotReadYet(ToolFailure):
    """The file exists and this run never read it: a write would be a guess about its content."""


class StaleRead(ToolFailure):
    """The file is different from the version the model last read or wrote: refuse instead of overwriting."""


class PartialRead(ToolFailure):
    """write_file replaces everything, so the model must have seen everything."""


class LineNumbersStale(ToolFailure):
    """A write since the last read_file moved the line numbers; edit_lines would hit the wrong lines."""


class InvalidRange(ToolFailure):
    """start_line and end_line do not describe lines of the file."""


class InvalidArgument(ToolFailure):
    """An argument of the wrong type or an empty old string."""


class OldStringNotFound(ToolFailure):
    """edit_file's old text is not in the file."""


class OldStringNotUnique(ToolFailure):
    """edit_file's old text matches more than once, so the edit would be a guess about which one."""


class WriteFailed(ToolFailure):
    """The operating system refused the write (permissions, disk); the file is as it was."""


class NoOpEdit(ToolFailure):
    """The edit would leave the file exactly as it is."""


@dataclass
class View:
    """What the model has seen of one file: the version, whether all of it, whether its line numbers still hold.

    ``covered`` collects the line numbers of partial reads of this version, so reading 1-200 and then 201-400
    of a 400-line file counts as having seen all of it.
    """
    digest: str
    full: bool
    numbered: bool
    covered: frozenset = frozenset()


def split_lines(text: str) -> list[str]:
    """Lines with their line ends kept. Only \\n ends a line (str.splitlines also splits on form feeds and
    Unicode separators), so the numbers match what an editor shows and what edit_lines counts."""
    return re.findall(r"[^\n]*\n|[^\n]+", text)


def syntax_report(rel: str, text: str) -> dict | None:
    """Compile Python files without running them, so the model hears about a syntax error right after the write."""
    if not rel.endswith(".py"):
        return None
    try:
        compile(text, rel, "exec")
    except (SyntaxError, ValueError, RecursionError) as error:
        return {"ok": False, "line": getattr(error, "lineno", None), "error": getattr(error, "msg", str(error))}
    return {"ok": True}


def _atomic_write(target: Path, data: bytes):
    """Write next to the target and rename over it: a crash leaves the old file or the new one, never half."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=target.parent, prefix=".edit-", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        if target.exists():
            shutil.copymode(target, temp)
        os.replace(temp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise


class FileTools:
    def __init__(self, workspace: Workspace, texts, *, protected=DEFAULT_PROTECTED,
                 record: Callable[[dict], None] | None = None):
        self.workspace = workspace
        self.t = texts
        self.protected = tuple(protected)
        self._record = record or (lambda row: None)
        self.journal: list[dict] = []
        self.views: dict[str, View] = {}

    def tools(self) -> dict[str, Callable]:
        """The allowlist: the model can only reach these names."""
        return {"read_file": self.read_file, "write_file": self.write_file,
                "edit_file": self.edit_file, "edit_lines": self.edit_lines}

    # -- guards ------------------------------------------------------------
    def _path(self, path) -> tuple[Path, str]:
        try:
            resolved = self.workspace.resolve(path)
        except ValueError as error:
            # resolve() explains in English for developers; the model gets the run's language.
            raise PathOutsideWorkspace(self.t.path_outside.format(path=str(path)[:80])) from error
        return resolved, self.workspace.relative(resolved)

    def _load(self, resolved: Path, rel: str) -> tuple[str, str]:
        if not resolved.exists():
            raise FileNotFound(self.t.file_not_found.format(path=rel))
        if not resolved.is_file():
            raise NotATextFile(self.t.not_a_file.format(path=rel))
        if resolved.stat().st_size > MAX_FILE_BYTES:
            raise NotATextFile(self.t.file_too_large.format(path=rel, limit=MAX_FILE_BYTES))
        try:
            data = resolved.read_bytes()
        except OSError as error:
            raise NotATextFile(self.t.not_text.format(path=rel)) from error
        # NUL bytes never appear in text; a decode error alone is not a reliable binary signal.
        if b"\x00" in data[:8192]:
            raise NotATextFile(self.t.not_text.format(path=rel))
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise NotATextFile(self.t.not_text.format(path=rel)) from error
        return text, sha256_bytes(data)

    def _check_view(self, rel: str, current: str, *, need_full: bool, need_numbers: bool):
        view = self.views.get(rel)
        # 1. Never read: the model would be writing blind.
        if view is None:
            raise NotReadYet(self.t.not_read_yet.format(path=rel))
        # 2. Read, but the file is different now: somebody else wrote it (optimistic concurrency).
        if view.digest != current:
            raise StaleRead(self.t.stale_read.format(path=rel))
        if need_full and not view.full:
            raise PartialRead(self.t.partial_read.format(path=rel))
        # 3. Line numbers die with every write, because a write can shift every line below it.
        if need_numbers and not view.numbered:
            raise LineNumbersStale(self.t.line_numbers_stale.format(path=rel))

    # -- reading -----------------------------------------------------------
    def read_file(self, path, start_line=1, end_line=None) -> dict:
        resolved, rel = self._path(path)
        text, digest = self._load(resolved, rel)
        lines = split_lines(text)
        total = len(lines)
        # Models often send null for an optional argument: that means the default.
        start_line = 1 if start_line is None else start_line
        if type(start_line) is not int or (end_line is not None and type(end_line) is not int):
            raise InvalidArgument(self.t.invalid_argument.format(name="start_line, end_line"))
        end = min(total, start_line + READ_LIMIT_LINES - 1) if end_line is None else min(end_line, total)
        if start_line < 1 or (total and (start_line > total or end < start_line)):
            raise InvalidRange(self.t.invalid_range.format(start=start_line, end=end_line, total=total))
        shown = [f"{number:>4}| {line.rstrip(chr(10))}" for number, line in enumerate(lines[start_line - 1:end], start_line)]
        previous = self.views.get(rel)
        same = previous is not None and previous.digest == digest
        covered = (previous.covered if same else frozenset()) | frozenset(range(start_line, end + 1))
        self.views[rel] = View(digest, bool(same and previous.full) or len(covered) == total, True, covered)
        return {"path": rel, "version": digest[:12], "total_lines": total, "start_line": start_line,
                "end_line": end, "truncated": end < total, "content": "\n".join(shown)}

    # -- writing -----------------------------------------------------------
    def write_file(self, path, content) -> dict:
        def build(rel, text, exists):
            if not isinstance(content, str):
                raise InvalidArgument(self.t.invalid_argument.format(name="content"))
            return content
        return self._write("write_file", path, build, need_full=True)

    def edit_file(self, path, old, new) -> dict:
        def build(rel, text, exists):
            if not exists:
                raise FileNotFound(self.t.file_not_found.format(path=rel))
            if not isinstance(old, str) or not old:
                raise InvalidArgument(self.t.old_empty)
            if not isinstance(new, str):
                raise InvalidArgument(self.t.invalid_argument.format(name="new"))
            lines, start = [], 0
            while (index := text.find(old, start)) >= 0:
                lines.append(text.count("\n", 0, index) + 1)
                start = index + len(old)
            # The one rule of this strategy: old must match exactly once.
            if not lines:
                raise OldStringNotFound(self.t.old_not_found.format(path=rel))
            if len(lines) > 1:
                shown = ", ".join(str(number) for number in lines[:5])
                raise OldStringNotUnique(self.t.old_not_unique.format(count=len(lines), lines=shown))
            if old == new:
                raise NoOpEdit(self.t.no_op_edit)
            return text.replace(old, new, 1)
        return self._write("edit_file", path, build)

    def edit_lines(self, path, start_line, end_line, new_text) -> dict:
        def build(rel, text, exists):
            if not exists:
                raise FileNotFound(self.t.file_not_found.format(path=rel))
            lines = split_lines(text)
            if (type(start_line) is not int or type(end_line) is not int
                    or not 1 <= start_line <= end_line <= len(lines)):
                raise InvalidRange(self.t.invalid_range.format(start=start_line, end=end_line, total=len(lines)))
            if not isinstance(new_text, str):
                raise InvalidArgument(self.t.invalid_argument.format(name="new_text"))
            replaced = "".join(lines[start_line - 1:end_line])
            # Keep the line structure: a replacement block ends with a newline when the lines it replaces did.
            block = new_text + "\n" if new_text and not new_text.endswith("\n") and replaced.endswith("\n") else new_text
            result = "".join(lines[:start_line - 1]) + block + "".join(lines[end_line:])
            if result == text:
                raise NoOpEdit(self.t.no_op_edit)
            return result
        return self._write("edit_lines", path, build, need_numbers=True)

    def _write(self, tool: str, path, build, *, need_full: bool = False, need_numbers: bool = False) -> dict:
        """The frame every write shares: guards, build the new text, write atomically, journal the evidence."""
        rel, before = str(path)[:80], None
        try:
            resolved, rel = self._path(path)
            if any(fnmatch.fnmatch(rel, pattern) for pattern in self.protected):
                raise ProtectedPath(self.t.protected_path.format(path=rel))
            exists = resolved.exists()
            old_text = None
            if exists:
                old_text, before = self._load(resolved, rel)
                self._check_view(rel, before, need_full=need_full, need_numbers=need_numbers)
            new_text = build(rel, old_text, exists)
        except ToolFailure as error:
            self._journal(tool, rel, ok=False, error_type=type(error).__name__, before=before, after=before)
            raise
        changed = new_text != old_text
        data = new_text.encode("utf-8")
        after = sha256_bytes(data)
        if changed:
            try:
                _atomic_write(resolved, data)
            except OSError as error:
                self._journal(tool, rel, ok=False, error_type="WriteFailed", before=before, after=before)
                raise WriteFailed(self.t.write_failed.format(path=rel)) from error
        diff, added, removed = unified_diff(rel, old_text, new_text) if changed else ("", 0, 0)
        syntax = syntax_report(rel, new_text)
        previous = self.views.get(rel)
        # The model knows the whole new content when it wrote it all, or edited a file it had read in full.
        full = tool == "write_file" or bool(previous and previous.full)
        self.views[rel] = View(after, full, numbered=False)
        self._journal(tool, rel, ok=True, changed=changed, created=old_text is None, before=before, after=after,
                      added=added, removed=removed, diff=diff, syntax_ok=None if syntax is None else syntax["ok"])
        # The model sees short versions and counts; the full hashes and the diff live in the journal and the events.
        return {"path": rel, "changed": changed, "created": old_text is None,
                "previous_version": before[:12] if before else None, "version": after[:12],
                "added": added, "removed": removed, "total_lines": len(split_lines(new_text)), "syntax": syntax}

    def _journal(self, tool: str, rel: str, *, ok: bool, before: str | None, after: str | None, changed: bool = False,
                 created: bool = False, error_type: str | None = None, added: int = 0, removed: int = 0,
                 diff: str = "", syntax_ok: bool | None = None):
        row = {"seq": len(self.journal) + 1, "tool": tool, "path": rel, "ok": ok, "changed": changed,
               "created": created, "error_type": error_type, "before_sha256": before, "after_sha256": after,
               "added": added, "removed": removed, "syntax_ok": syntax_ok, "diff": diff}
        self.journal.append(row)
        self._record(row)
