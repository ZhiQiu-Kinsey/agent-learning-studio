"""Split documents into chunks that still know where they came from.

Structure first, size second: a whole section is kept together when it fits the budget;
only a section that is too long falls back to its lines (each handbook line is one
paragraph or list item, so no sentence is ever cut). Units are then packed into chunks,
and `overlap_lines` repeats the last lines of a chunk at the start of the next one so
the context just before a boundary is not lost. Every chunk is an exact line range of
the original file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from lessons.lesson_document_loading.loader import Document, load_corpus

HEADING = re.compile(r"^#{1,6}\s.*?(?:\{#(?P<anchor>[a-z0-9-]+)\})?\s*$")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # f"{doc_id}:{start_line}-{end_line}", stable while the file is unchanged
    doc_id: str
    path: str
    title: str
    version: str
    start_line: int  # 1-based lines of the original file, front matter included
    end_line: int
    anchors: tuple[str, ...]  # sections this chunk touches, as "doc_id#anchor"
    text: str
    trust: str
    supersedes: tuple[str, ...] = ()  # doc_ids that this chunk's document replaces


@dataclass(frozen=True)
class ChunkingParams:
    max_chars: int
    overlap_lines: int

    def __post_init__(self):
        if self.max_chars < 1 or self.overlap_lines < 0:
            raise ValueError("max_chars must be >= 1 and overlap_lines >= 0")


# The same content takes about 2.5 times as many characters in English as in Chinese,
# so each language gets its own character budget; the line overlap is the same.
PRESETS = {
    "default": {"zh-CN": ChunkingParams(max_chars=150, overlap_lines=1),
                "en": ChunkingParams(max_chars=450, overlap_lines=1)},
    "narrow": {"zh-CN": ChunkingParams(max_chars=60, overlap_lines=0),
               "en": ChunkingParams(max_chars=150, overlap_lines=0)},
}
DEFAULT_PARAMS = PRESETS["default"]["zh-CN"]


@dataclass(frozen=True)
class Line:
    number: int  # line number in the original file
    text: str
    anchor: str | None  # section the line belongs to


def params_for(locale: str, preset: str = "default") -> ChunkingParams:
    return PRESETS[preset][locale]


def chunk_document(doc: Document, params: ChunkingParams | None = None) -> list[Chunk]:
    """params=None uses the default budget of the document's language."""
    params = params or params_for(doc.locale)
    units = section_units(content_lines(doc), params.max_chars)
    return [make_chunk(doc, group) for group in pack(units, params)]


def content_lines(doc: Document) -> list[Line]:
    lines, anchor = [], None
    for number, text in enumerate(doc.text.split("\n"), start=doc.line_offset + 1):
        if not text.strip():
            continue
        heading = HEADING.match(text)
        if heading:
            anchor = heading.group("anchor")
        lines.append(Line(number, text, anchor))
    return lines


def section_units(lines: list[Line], max_chars: int) -> list[list[Line]]:
    units = []
    for section in split_sections(lines):
        if size(section) <= max_chars:
            units.append(section)
        else:
            units.extend(line_units(section))
    return units


def split_sections(lines: list[Line]) -> list[list[Line]]:
    sections = []
    for line in lines:
        if not sections or HEADING.match(line.text):
            sections.append([])
        sections[-1].append(line)
    return sections


def line_units(section: list[Line]) -> list[list[Line]]:
    # A heading alone at the end of a chunk says nothing; glue it to the line it introduces.
    if len(section) > 1 and HEADING.match(section[0].text):
        return [section[:2]] + [[line] for line in section[2:]]
    return [[line] for line in section]


def pack(units: list[list[Line]], params: ChunkingParams) -> list[list[Line]]:
    groups, current = [], []
    for unit in units:
        if current and size(current) + size(unit) > params.max_chars:
            groups.append(current)
            current = overlap(current, params.overlap_lines)
        current = current + unit
    if current:
        groups.append(current)
    return groups


def size(lines: list[Line]) -> int:
    return sum(len(line.text) for line in lines)


def overlap(group: list[Line], count: int) -> list[Line]:
    # Never carry the whole previous chunk, or the next one would contain it entirely.
    keep = min(count, len(group) - 1)
    return group[len(group) - keep:] if keep > 0 else []


def make_chunk(doc: Document, group: list[Line]) -> Chunk:
    start, end = group[0].number, group[-1].number
    body = doc.text.split("\n")
    text = "\n".join(body[start - doc.line_offset - 1:end - doc.line_offset])
    anchors = tuple(dict.fromkeys(f"{doc.doc_id}#{line.anchor}" for line in group if line.anchor))
    supersedes = tuple(part.strip() for part in doc.meta.get("supersedes", "").split(",") if part.strip())
    return Chunk(chunk_id=f"{doc.doc_id}:{start}-{end}", doc_id=doc.doc_id, path=doc.path, title=doc.title,
                 version=doc.version, start_line=start, end_line=end, anchors=anchors, text=text,
                 trust=doc.trust, supersedes=supersedes)


def chunk_corpus(docs: list[Document], params: ChunkingParams | None = None) -> list[Chunk]:
    return [chunk for doc in docs for chunk in chunk_document(doc, params)]


def default_chunks(locale: str) -> list[Chunk]:
    """The standard chunk list every later lesson indexes."""
    documents, _ = load_corpus(locale)
    return chunk_corpus(documents)
