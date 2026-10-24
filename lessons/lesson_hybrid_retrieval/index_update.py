"""Keep a saved vector index in step with a corpus that changes.

The lesson never touches the handbook in the repository: it copies it into a working
folder under .runtime/ and edits that copy. Next to the vectors it saves a fingerprint
(hash of the embedded text) per chunk; comparing fingerprints tells which chunks are new,
changed, removed or unchanged, so only new and changed text is embedded again and removed
chunks leave the index instead of lingering as evidence.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from lessons.lesson_document_loading.chunking import Chunk
from lessons.lesson_document_loading.loader import CORPUS_DIR, ROOT, Document, corpus_files, load_file
from lessons.lesson_embedding_retrieval.vector_index import VectorIndex
from lessons.lesson_keyword_retrieval.bm25 import Hit

# Git-ignored; tests point this at a temporary folder (it must stay under ROOT so paths stay repo-relative).
WORKSPACE = ROOT / ".runtime" / "hybrid-retrieval"
MANIFEST_FORMAT = 1
# The scripted change: one number in one rule, and one superseded document taken down.
EDITED_FILE, OLD_VALUE, NEW_VALUE, NEW_VERSION = "fees.md", "0.5", "0.3", "2026-10"
DELETED_FILE = "hours-2025.md"


def working_folder(locale: str) -> Path:
    return WORKSPACE / locale


def reset_working_copy(locale: str) -> Path:
    """A fresh copy of the clean corpus, so every run starts from the same files."""
    folder = working_folder(locale) / "corpus"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for source in sorted((CORPUS_DIR / locale).glob("*.md")):
        shutil.copyfile(source, folder / source.name)
    return folder


def load_folder(folder: Path, locale: str) -> list[Document]:
    """Load one folder with the shared loader; a broken file is an error here, not a skipped document."""
    documents = []
    for path in corpus_files([folder]):
        document, issue = load_file(path, locale)
        if issue:
            raise ValueError(f"{issue.path}: {issue.kind}: {issue.detail}")
        documents.append(document)
    return documents


def folder_version(documents: list[Document]) -> str:
    # The same digest as loader.corpus_version, computed over this folder instead of the repository corpus.
    lines = sorted(f"{doc.doc_id}:{doc.sha256}" for doc in documents)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def file_digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else None


def apply_changes(folder: Path) -> list[dict]:
    """Edit one rule and delete one file in the working copy; each record has the hashes before and after."""
    edited, deleted = folder / EDITED_FILE, folder / DELETED_FILE
    records = [{"file": EDITED_FILE, "action": "edit", "before": file_digest(edited)},
               {"file": DELETED_FILE, "action": "delete", "before": file_digest(deleted)}]
    lines = edited.read_text(encoding="utf-8").split("\n")
    # Only the first body line holding the value changes; the version line says the document was revised.
    target = next(i for i, line in enumerate(lines) if OLD_VALUE in line and not line.startswith("version:"))
    lines[target] = lines[target].replace(OLD_VALUE, NEW_VALUE, 1)
    lines = [f"version: {NEW_VERSION}" if line.startswith("version:") else line for line in lines]
    edited.write_text("\n".join(lines), encoding="utf-8")
    deleted.unlink()
    records[0]["after"], records[1]["after"] = file_digest(edited), None
    records[0]["line"] = target + 1
    return records


def fingerprints(chunks: list[Chunk]) -> dict[str, str]:
    """Hash of exactly the text that was embedded: if it changes, the old vector no longer describes the chunk."""
    return {chunk.chunk_id: hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()[:16] for chunk in chunks}


def plan_update(saved: dict[str, str], current: dict[str, str]) -> dict[str, list[str]]:
    return {
        "added": [cid for cid in current if cid not in saved],
        "changed": [cid for cid in current if cid in saved and saved[cid] != current[cid]],
        "removed": [cid for cid in saved if cid not in current],
        "unchanged": [cid for cid in current if saved.get(cid) == current[cid]],
    }


def apply_update(index: VectorIndex, chunks: list[Chunk], new_vectors: dict[str, list[float]],
                 corpus_version: str) -> VectorIndex:
    """Rebuild the index in current chunk order: fresh vectors for new and changed chunks, kept ones for the rest.

    Removed chunks are simply not carried over. Mixing vectors from two models would make
    cosines meaningless, so a dimension change is refused rather than patched.
    """
    kept = dict(zip(index.chunk_ids, index.vectors))
    vectors = []
    for chunk in chunks:
        vector = new_vectors.get(chunk.chunk_id, kept.get(chunk.chunk_id))
        if vector is None:
            raise ValueError(f"no vector for chunk {chunk.chunk_id}")
        vectors.append(vector)
    if any(len(vector) != index.dimensions for vector in vectors):
        raise ValueError("new vectors have a different size; rebuild the whole index instead")
    return VectorIndex(index.model, index.dimensions, corpus_version, [c.chunk_id for c in chunks], vectors)


def save(index: VectorIndex, prints: dict[str, str], folder: Path) -> None:
    """Vectors first, manifest second: a manifest never describes vectors that were not written."""
    index.save(folder / "vectors.json")
    manifest = {"format": MANIFEST_FORMAT, "corpus_version": index.corpus_version, "model": index.model,
                "dimensions": index.dimensions, "fingerprints": prints}
    temporary = folder / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    temporary.replace(folder / "manifest.json")


def load(folder: Path) -> tuple[VectorIndex, dict[str, str]]:
    """What a restarted process sees: only the files on disk, checked against each other."""
    index = VectorIndex.load(folder / "vectors.json")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError(f"unsupported manifest format {manifest.get('format')!r}")
    if (manifest["corpus_version"], manifest["model"], manifest["dimensions"]) != (
            index.corpus_version, index.model, index.dimensions):
        raise ValueError("manifest and vectors were written for different builds")
    if set(manifest["fingerprints"]) != set(index.chunk_ids):
        raise ValueError("manifest and vectors list different chunks")
    return index, manifest["fingerprints"]


def stale_hits(hits: list[Hit], saved: dict[str, str], current: dict[str, str]) -> list[dict]:
    """Hits that must not be used as current evidence: the source is gone, or its text changed since embedding."""
    stale = []
    for hit in hits:
        if hit.chunk_id not in current:
            stale.append({"chunk_id": hit.chunk_id, "reason": "source_missing"})
        elif saved.get(hit.chunk_id) != current[hit.chunk_id]:
            stale.append({"chunk_id": hit.chunk_id, "reason": "text_changed"})
    return stale
