"""Load the Bluestone Library Handbook from local Markdown files.

Each document keeps its path, version and content hash so that every chunk and citation
built later can be traced back to one exact file. Text read from files is data: it is
marked untrusted here, at the first step, because nothing after this point can tell a
handbook rule from a sentence someone typed into a comment form.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
# Broken samples live beside the real corpus so the default load stays clean.
PROBLEM_DIR = CORPUS_DIR / "problems"

SUPPORTED_SUFFIXES = (".md",)
REQUIRED_KEYS = ("doc_id", "title", "version")
UNTRUSTED = "untrusted_data"
# Short lines (a price, a list label) repeat by coincidence; only longer lines count as copied text.
MIN_DUPLICATE_CHARS = 16


@dataclass(frozen=True)
class Document:
    doc_id: str
    path: str  # repository-relative POSIX path
    title: str
    version: str
    text: str  # body without the front matter, line count unchanged
    sha256: str  # hash of the file bytes on disk
    trust: str
    meta: dict  # remaining front matter keys, e.g. supersedes
    locale: str = "zh-CN"
    line_offset: int = 0  # file lines before the body; body line n is file line n + line_offset


@dataclass(frozen=True)
class LoadIssue:
    path: str
    kind: str  # "empty" | "duplicate" | "parse_error" | "unsupported"
    detail: str  # for developers; lessons translate `kind` for learners


class ParseError(ValueError):
    pass


def load_corpus(locale: str, *, include_problem_files: bool = False) -> tuple[list[Document], list[LoadIssue]]:
    """Load every file of one language; problems are reported, never skipped silently."""
    folders = [CORPUS_DIR / locale]
    if not folders[0].is_dir():
        raise ValueError(f"no corpus for locale {locale!r}")
    if include_problem_files:
        folders.append(PROBLEM_DIR / locale)
    documents, issues = [], []
    seen_ids: dict[str, str] = {}
    seen_lines: dict[str, tuple[str, int]] = {}
    for path in corpus_files(folders):
        document, issue = load_file(path, locale)
        if issue:
            issues.append(issue)
            continue
        if document.doc_id in seen_ids:
            issues.append(LoadIssue(document.path, "duplicate",
                                    f"doc_id {document.doc_id!r} is already used by {seen_ids[document.doc_id]}"))
            continue
        seen_ids[document.doc_id] = document.path
        issues.extend(find_repeated_lines(document, seen_lines))
        documents.append(document)
    return documents, issues


def corpus_files(folders: list[Path]) -> list[Path]:
    # Sorted per folder so the load order, and therefore every chunk list, is reproducible.
    files = []
    for folder in folders:
        if folder.is_dir():
            files.extend(sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")))
    return files


def load_file(path: Path, locale: str) -> tuple[Document | None, LoadIssue | None]:
    relative = path.relative_to(ROOT).as_posix()
    if path.suffix not in SUPPORTED_SUFFIXES:
        return None, LoadIssue(relative, "unsupported", f"suffix {path.suffix!r} is not one of {SUPPORTED_SUFFIXES}")
    raw = path.read_bytes()
    try:
        text = clean(raw.decode("utf-8-sig"))
        meta, body, line_offset = split_front_matter(text)
    except UnicodeDecodeError as error:
        return None, LoadIssue(relative, "parse_error", f"not valid UTF-8: {error.reason} at byte {error.start}")
    except ParseError as error:
        return None, LoadIssue(relative, "parse_error", str(error))
    if not body.strip():
        return None, LoadIssue(relative, "empty", "front matter is present but the body has no text")
    return Document(
        doc_id=meta.pop("doc_id"), path=relative, title=meta.pop("title"), version=meta.pop("version"),
        text=body, sha256=hashlib.sha256(raw).hexdigest(), trust=UNTRUSTED, meta=meta,
        locale=locale, line_offset=line_offset,
    ), None


def clean(text: str) -> str:
    # Cleaning must not add or remove lines: chunk line numbers point into the original file.
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def split_front_matter(text: str) -> tuple[dict, str, int]:
    lines = text.split("\n")
    if lines[0] != "---":
        raise ParseError("file does not start with a '---' front matter line")
    for index in range(1, len(lines)):
        if lines[index] == "---":
            return parse_meta(lines[1:index]), "\n".join(lines[index + 1:]), index + 1
    raise ParseError("front matter is never closed with a second '---' line")


def parse_meta(lines: list[str]) -> dict:
    meta = {}
    for line in lines:
        if not line.strip():
            continue
        key, colon, value = line.partition(":")
        if not colon or not key.strip():
            raise ParseError(f"front matter line is not 'key: value': {line!r}")
        meta[key.strip()] = value.strip()
    missing = [key for key in REQUIRED_KEYS if not meta.get(key)]
    if missing:
        raise ParseError(f"front matter is missing {', '.join(missing)}")
    return meta


def find_repeated_lines(document: Document, seen: dict[str, tuple[str, int]]) -> list[LoadIssue]:
    """Record lines copied from an earlier file; the copy stays loaded so learners can see it retrieved twice."""
    issues = []
    for number, line in enumerate(document.text.split("\n"), start=document.line_offset + 1):
        key = " ".join(line.split())
        if len(key) < MIN_DUPLICATE_CHARS or key.startswith("#"):
            continue
        if key in seen:
            first_path, first_line = seen[key]
            issues.append(LoadIssue(document.path, "duplicate", f"line {number} repeats {first_path} line {first_line}"))
        else:
            seen[key] = (document.path, number)
    return issues


def corpus_version(locale: str) -> str:
    """One digest over all clean documents: any edit, addition or removal changes it."""
    documents, _ = load_corpus(locale)
    lines = sorted(f"{doc.doc_id}:{doc.sha256}" for doc in documents)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]
