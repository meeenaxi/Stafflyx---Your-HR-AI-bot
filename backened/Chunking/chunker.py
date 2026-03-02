"""
NovaCorp HR AI - Hybrid Chunking Engine
Supports: PDF, DOCX, Markdown, MP4 metadata, Images, JSON links
Strategy: Semantic chunking for docs, metadata chunking for media
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging

from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_MIN_SIZE

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_chunk_id(file_name: str, index: int, text: str) -> str:
    content = f"{file_name}_{index}_{text[:50]}"
    return hashlib.md5(content.encode()).hexdigest()


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences for semantic chunking."""
    # Split on sentence boundaries while keeping reasonable granularity
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if s.strip()]


def _semantic_chunk(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Semantic chunking: builds chunks by accumulating sentences until
    chunk_size (estimated in chars, ~4 chars/token) is reached.
    Overlap is carried forward from the end of the previous chunk.
    """
    char_limit = chunk_size * 4
    overlap_chars = overlap * 4

    sentences = _split_into_sentences(text)
    if not sentences:
        return [text] if text.strip() else []

    chunks = []
    current_chunk = []
    current_len = 0

    for sentence in sentences:
        sent_len = len(sentence)
        if current_len + sent_len > char_limit and current_chunk:
            chunk_text = " ".join(current_chunk)
            if len(chunk_text) >= CHUNK_MIN_SIZE * 4:
                chunks.append(chunk_text)
            # Overlap: keep last few sentences
            overlap_text = ""
            overlap_sents = []
            for s in reversed(current_chunk):
                if len(overlap_text) + len(s) <= overlap_chars:
                    overlap_sents.insert(0, s)
                    overlap_text += len(s)
                else:
                    break
            current_chunk = overlap_sents
            current_len = sum(len(s) for s in current_chunk)

        current_chunk.append(sentence)
        current_len += sent_len

    if current_chunk:
        chunk_text = " ".join(current_chunk)
        if len(chunk_text) >= CHUNK_MIN_SIZE * 4:
            chunks.append(chunk_text)

    return chunks if chunks else [text[:char_limit]]


def _base_metadata(file_path: Path, source_type: str, category: str) -> Dict[str, Any]:
    return {
        "source_type": source_type,
        "file_name": file_path.name,
        "file_path": str(file_path),
        "category": category,
        "admin_uploaded": True,
        "timestamp": datetime.now().isoformat(),
        "url": ""
    }


# ─── Per-type chunkers ────────────────────────────────────────────────────────

def chunk_markdown(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """Semantic chunking for .md files."""
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    # Remove markdown headers for cleaner text but keep section context
    # Split on H2/H3 headers first for section-aware chunking
    sections = re.split(r'\n#{1,3} ', text)
    chunks = []
    idx = 0
    for section in sections:
        section = section.strip()
        if not section:
            continue
        for chunk_text in _semantic_chunk(section):
            meta = _base_metadata(file_path, "markdown", category)
            meta["chunk_index"] = idx
            chunks.append({
                "id": _make_chunk_id(file_path.name, idx, chunk_text),
                "text": chunk_text,
                "metadata": meta
            })
            idx += 1
    logger.info(f"Chunked {file_path.name} → {len(chunks)} chunks")
    return chunks


def chunk_pdf(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """Extract text from PDF and apply semantic chunking."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(file_path))
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
    except ImportError:
        logger.warning("pypdf not installed; treating PDF as empty.")
        full_text = f"[PDF document: {file_path.name}. Install pypdf to extract text.]"
    except Exception as e:
        logger.error(f"Error reading PDF {file_path}: {e}")
        full_text = f"[Could not extract text from {file_path.name}]"

    chunks = []
    for idx, chunk_text in enumerate(_semantic_chunk(full_text)):
        meta = _base_metadata(file_path, "pdf", category)
        meta["chunk_index"] = idx
        chunks.append({
            "id": _make_chunk_id(file_path.name, idx, chunk_text),
            "text": chunk_text,
            "metadata": meta
        })
    logger.info(f"Chunked PDF {file_path.name} → {len(chunks)} chunks")
    return chunks


def chunk_docx(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """Extract text from DOCX and apply semantic chunking."""
    try:
        from docx import Document
        doc = Document(str(file_path))
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    except ImportError:
        logger.warning("python-docx not installed.")
        full_text = f"[DOCX document: {file_path.name}. Install python-docx to extract text.]"
    except Exception as e:
        logger.error(f"Error reading DOCX {file_path}: {e}")
        full_text = f"[Could not extract text from {file_path.name}]"

    chunks = []
    for idx, chunk_text in enumerate(_semantic_chunk(full_text)):
        meta = _base_metadata(file_path, "docx", category)
        meta["chunk_index"] = idx
        chunks.append({
            "id": _make_chunk_id(file_path.name, idx, chunk_text),
            "text": chunk_text,
            "metadata": meta
        })
    logger.info(f"Chunked DOCX {file_path.name} → {len(chunks)} chunks")
    return chunks


def chunk_video_metadata(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """
    For video files: chunk from companion metadata JSON if exists,
    otherwise create a single metadata chunk from the filename.
    Frame/metadata chunking strategy.
    """
    # Look for a companion JSON metadata file
    meta_json_path = file_path.with_suffix(".json")
    video_meta = {}

    # Check training_videos.json in same directory
    training_json = file_path.parent / "training_videos.json"
    if training_json.exists():
        try:
            entries = json.loads(training_json.read_text())
            for entry in entries:
                if entry.get("file") == file_path.name:
                    video_meta = entry
                    break
        except Exception:
            pass

    if not video_meta:
        video_meta = {"title": file_path.stem, "description": f"Video: {file_path.name}"}

    title = video_meta.get("title", file_path.stem)
    description = video_meta.get("description", "")
    topics = video_meta.get("topics", [])
    duration = video_meta.get("duration_minutes", "unknown")
    url = video_meta.get("url", "")

    chunk_text = (
        f"Video Training Resource: {title}\n"
        f"Duration: {duration} minutes\n"
        f"Description: {description}\n"
        f"Topics covered: {', '.join(topics) if topics else 'General HR training'}\n"
        f"Access this video at: {url or 'NovaCorp Learning Portal'}"
    )

    meta = _base_metadata(file_path, "video", category)
    meta["url"] = url
    meta["title"] = title
    meta["duration_minutes"] = str(duration)

    return [{
        "id": _make_chunk_id(file_path.name, 0, chunk_text),
        "text": chunk_text,
        "metadata": meta
    }]


def chunk_image(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """
    For images: create a metadata/caption chunk.
    In production, this would use a vision model for caption extraction.
    """
    # Generate descriptive text from filename (production: use BLIP/LLaVA)
    name_clean = file_path.stem.replace("_", " ").replace("-", " ").title()

    chunk_text = (
        f"HR Resource Image: {name_clean}\n"
        f"File: {file_path.name}\n"
        f"Category: {category}\n"
        f"This image is an HR visual resource. "
        f"To view this image, access the HR Knowledge Base image gallery."
    )

    meta = _base_metadata(file_path, "image", category)
    meta["title"] = name_clean

    return [{
        "id": _make_chunk_id(file_path.name, 0, chunk_text),
        "text": chunk_text,
        "metadata": meta
    }]


def chunk_links_json(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """
    URL metadata extraction chunking.
    Each link entry becomes its own chunk.
    """
    try:
        entries = json.loads(file_path.read_text())
    except Exception as e:
        logger.error(f"Error reading links JSON {file_path}: {e}")
        return []

    chunks = []
    for idx, entry in enumerate(entries):
        title = entry.get("title", "HR Resource")
        url = entry.get("url", "")
        description = entry.get("description", "")
        tags = entry.get("tags", [])
        link_category = entry.get("category", category)

        chunk_text = (
            f"HR Link Resource: {title}\n"
            f"URL: {url}\n"
            f"Description: {description}\n"
            f"Category: {link_category}\n"
            f"Keywords: {', '.join(tags)}"
        )

        meta = _base_metadata(file_path, "link", category)
        meta["url"] = url
        meta["title"] = title

        chunks.append({
            "id": _make_chunk_id(file_path.name, idx, chunk_text),
            "text": chunk_text,
            "metadata": meta
        })

    logger.info(f"Chunked links JSON {file_path.name} → {len(chunks)} chunks")
    return chunks


def chunk_training_videos_json(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """Chunk training_videos.json where each entry is a video metadata record."""
    try:
        entries = json.loads(file_path.read_text())
    except Exception as e:
        logger.error(f"Error reading training JSON {file_path}: {e}")
        return []

    chunks = []
    for idx, entry in enumerate(entries):
        title = entry.get("title", "Training Video")
        url = entry.get("url", "")
        description = entry.get("description", "")
        topics = entry.get("topics", [])
        duration = entry.get("duration_minutes", "unknown")

        chunk_text = (
            f"Video Training Resource: {title}\n"
            f"Duration: {duration} minutes\n"
            f"Description: {description}\n"
            f"Topics covered: {', '.join(topics)}\n"
            f"Watch at: {url}"
        )

        meta = _base_metadata(file_path, "video", category)
        meta["url"] = url
        meta["title"] = title
        meta["duration_minutes"] = str(duration)

        chunks.append({
            "id": _make_chunk_id(file_path.name + str(idx), idx, chunk_text),
            "text": chunk_text,
            "metadata": meta
        })

    logger.info(f"Chunked training videos JSON → {len(chunks)} video chunks")
    return chunks


# ─── Dispatcher ───────────────────────────────────────────────────────────────

def chunk_file(file_path: Path, category: str) -> List[Dict[str, Any]]:
    """Dispatch to the correct chunker based on file type."""
    suffix = file_path.suffix.lower()
    name = file_path.name.lower()

    if suffix == ".md" or suffix == ".txt":
        return chunk_markdown(file_path, category)
    elif suffix == ".pdf":
        return chunk_pdf(file_path, category)
    elif suffix == ".docx":
        return chunk_docx(file_path, category)
    elif suffix in [".mp4", ".avi", ".mov", ".mkv"]:
        return chunk_video_metadata(file_path, category)
    elif suffix in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        return chunk_image(file_path, category)
    elif suffix == ".json":
        # Distinguish training vs links JSON
        if "training" in name:
            return chunk_training_videos_json(file_path, category)
        else:
            return chunk_links_json(file_path, category)
    else:
        logger.warning(f"Unsupported file type: {suffix} for {file_path.name}")
        return []
