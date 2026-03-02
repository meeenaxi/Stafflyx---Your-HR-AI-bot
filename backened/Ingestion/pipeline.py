"""
NovaCorp HR AI - Knowledge Base Ingestion Pipeline
Scans all KB folders, chunks content, and upserts to ChromaDB.
Admin-only operation.

NOTE: All functions here are synchronous and intended to be called via
asyncio.to_thread() from async route handlers. They use add_chunks_sync()
and query_sync() on the VectorStore to avoid nested event loop issues.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

from config.settings import (
    KB_CATEGORIES,
    SUPPORTED_DOC_TYPES, SUPPORTED_VIDEO_TYPES,
    SUPPORTED_IMAGE_TYPES, SUPPORTED_LINK_FILES
)
from backend.chunking.chunker import chunk_file
from backend.vector_db.chroma_store import get_vector_store

logger = logging.getLogger(__name__)

ALL_SUPPORTED = (
    SUPPORTED_DOC_TYPES + SUPPORTED_VIDEO_TYPES +
    SUPPORTED_IMAGE_TYPES + SUPPORTED_LINK_FILES
)


def get_all_kb_files() -> List[Tuple[Path, str]]:
    """Return (file_path, category) for every file in the knowledge base."""
    files = []
    for category, folder in KB_CATEGORIES.items():
        folder.mkdir(parents=True, exist_ok=True)
        for fp in folder.iterdir():
            if fp.is_file() and fp.suffix.lower() in ALL_SUPPORTED:
                files.append((fp, category))
    return files


def ingest_file(file_path: Path, category: str) -> int:
    """
    Chunk a single file and upsert to ChromaDB. Returns chunk count.
    Uses add_chunks_sync() — safe to call from a thread (via asyncio.to_thread).
    """
    vs = get_vector_store()
    chunks = chunk_file(file_path, category)
    if not chunks:
        logger.warning(f"No chunks generated for {file_path.name}")
        return 0
    # Use the sync variant — this function is always run inside a thread
    count = vs.add_chunks_sync(chunks)
    return count


def ingest_all(reset: bool = False) -> Dict[str, Any]:
    """
    Full re-index of all KB files.
    If reset=True, wipes the collection first.
    Returns summary stats.

    Designed to be called via: await asyncio.to_thread(ingest_all, reset=True)
    """
    vs = get_vector_store()
    if reset:
        vs.reset_collection()
        logger.info("Collection reset. Starting fresh index.")

    files = get_all_kb_files()
    total_chunks = 0
    results = []

    for file_path, category in files:
        try:
            count = ingest_file(file_path, category)
            results.append({"file": file_path.name, "category": category, "chunks": count, "status": "ok"})
            total_chunks += count
            logger.info(f"{file_path.name} ({category}) → {count} chunks")
        except Exception as e:
            logger.error(f"{file_path.name}: {e}")
            results.append({"file": file_path.name, "category": category, "chunks": 0, "status": f"error: {e}"})

    return {
        "total_files": len(files),
        "total_chunks": total_chunks,
        "results": results
    }


def save_uploaded_file(
    file_bytes: bytes,
    file_name: str,
    category: str
) -> Path:
    """
    Save an admin-uploaded file to the appropriate KB folder.
    Returns the saved file path.
    """
    folder = KB_CATEGORIES.get(category)
    if not folder:
        raise ValueError(f"Unknown category: {category}")
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / file_name
    with open(dest, "wb") as f:
        f.write(file_bytes)
    logger.info(f"Saved upload: {dest}")
    return dest


def ingest_uploaded_file(file_bytes: bytes, file_name: str, category: str) -> Dict[str, Any]:
    """
    Save an uploaded file and immediately index it.
    Returns result summary.

    Designed to be called via: await asyncio.to_thread(ingest_uploaded_file, ...)
    """
    file_path = save_uploaded_file(file_bytes, file_name, category)
    chunks = ingest_file(file_path, category)
    return {
        "file": file_name,
        "category": category,
        "chunks_indexed": chunks,
        "path": str(file_path)
    }


def delete_kb_file(file_name: str, category: str) -> Dict[str, Any]:
    """Delete a file from KB folder and remove its vectors from ChromaDB."""
    folder = KB_CATEGORIES.get(category)
    if not folder:
        raise ValueError(f"Unknown category: {category}")

    file_path = folder / file_name
    vs = get_vector_store()

    deleted_chunks = vs.delete_by_source(file_name)

    if file_path.exists():
        file_path.unlink()
        return {"status": "deleted", "file": file_name, "chunks_removed": deleted_chunks}
    return {"status": "file_not_found", "file": file_name, "chunks_removed": deleted_chunks}


def get_kb_overview() -> Dict[str, Any]:
    """Return a summary of the current knowledge base state."""
    files_by_cat = {}
    for category, folder in KB_CATEGORIES.items():
        folder.mkdir(parents=True, exist_ok=True)
        cat_files = [fp.name for fp in folder.iterdir()
                     if fp.is_file() and fp.suffix.lower() in ALL_SUPPORTED]
        files_by_cat[category] = cat_files

    vs = get_vector_store()
    stats = vs.get_stats()

    return {
        "kb_files": files_by_cat,
        "vector_stats": stats
    }