"""
NovaCorp HR AI - Source Attribution Agent
Builds structured source citations from retrieved chunks.
"""

from typing import List, Dict, Any


SOURCE_ICONS = {
    "pdf": "📄",
    "docx": "📝",
    "markdown": "📋",
    "md": "📋",
    "video": "🎬",
    "image": "🖼️",
    "link": "🔗",
    "unknown": "📁"
}


def build_source_citations(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a deduplicated list of source citations from retrieved chunks.

    Returns list of citation objects:
    {
        "icon": str,
        "source_type": str,
        "file_name": str,
        "category": str,
        "url": str,
        "title": str,
        "relevance_score": float,
        "excerpt": str  (first 120 chars of chunk text)
    }
    """
    seen_files = set()
    citations = []

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        file_name = meta.get("file_name", "Unknown")
        source_type = meta.get("source_type", "unknown")

        # Deduplicate by file_name
        if file_name in seen_files:
            continue
        seen_files.add(file_name)

        icon = SOURCE_ICONS.get(source_type, SOURCE_ICONS["unknown"])
        url = meta.get("url", "")
        title = meta.get("title", file_name)
        text = chunk.get("text", "")
        excerpt = text[:150].strip() + "..." if len(text) > 150 else text

        citations.append({
            "icon": icon,
            "source_type": source_type,
            "file_name": file_name,
            "category": meta.get("category", "general"),
            "url": url,
            "title": title,
            "relevance_score": chunk.get("reranked_score", chunk.get("score", 0.0)),
            "excerpt": excerpt
        })

    return citations


def format_sources_text(citations: List[Dict]) -> str:
    """Format citations as a markdown string for display."""
    if not citations:
        return ""

    lines = ["\n\n---\n**Sources:**"]
    for i, cite in enumerate(citations, 1):
        icon = cite["icon"]
        title = cite["title"]
        cat = cite["category"].title()
        score = cite["relevance_score"]
        url = cite.get("url", "")

        if url:
            lines.append(f"{i}. {icon} [{title}]({url}) — *{cat}* (relevance: {score:.0%})")
        else:
            lines.append(f"{i}. {icon} **{title}** — *{cat}* (relevance: {score:.0%})")

    return "\n".join(lines)
