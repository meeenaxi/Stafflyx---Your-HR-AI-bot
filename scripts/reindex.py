#!/usr/bin/env python3
"""
NovaCorp HR AI - Re-index CLI
Re-indexes the knowledge base from the command line.
Usage:
    python scripts/reindex.py           # incremental upsert
    python scripts/reindex.py --reset   # wipe and re-index
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')

from backend.ingestion.pipeline import ingest_all

if __name__ == "__main__":
    reset = "--reset" in sys.argv
    if reset:
        print("⚠️  Reset mode: wiping ChromaDB collection before re-indexing...")

    print("🔄 Starting re-index...\n")
    result = ingest_all(reset=reset)

    print(f"\n✅ Done! Files: {result['total_files']} | Chunks: {result['total_chunks']:,}\n")
    for r in result["results"]:
        icon = "✅" if r["status"] == "ok" else "❌"
        print(f"  {icon} {r['file']} ({r['category']}) → {r['chunks']} chunks | {r['status']}")
