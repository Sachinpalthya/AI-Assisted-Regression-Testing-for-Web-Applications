"""
pipeline/context_builder.py — Stage 1: Codebase Context Builder (RAG)

Walks the project folder, reads all source files, chunks them, generates 
embeddings via Ollama, and stores them in a local ChromaDB instance.
Produces a high-level summary of the project and saves a lightweight context.json.
"""

import logging
from pathlib import Path
from typing import Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from utils.file_utils import iter_source_files, read_file_content, save_json, ensure_output_dirs
from utils.ollama_client import generate, get_embedding

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger(__name__)


def build_context(project_root: Path) -> dict[str, Any]:
    """
    Stage 1 entry point.

    Scans `project_root` for source files, reads their content,
    chunks them, and stores them in ChromaDB. 
    Asks Ollama for a high-level project summary.

    Returns:
        context dict with keys: project_root, total_files, files (metadata only), summary
    """
    ensure_output_dirs()

    if not chromadb:
        logger.error("chromadb is not installed. Please install it to use RAG.")
        raise ImportError("chromadb is required for RAG.")

    logger.info(f"[Stage 1] Scanning project: {project_root}")
    
    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))
    try:
        chroma_client.delete_collection("project_context")
    except Exception:
        pass
    collection = chroma_client.create_collection(name="project_context")

    files_metadata = []
    all_files = list(iter_source_files(project_root))
    logger.info(f"  Found {len(all_files)} source file(s)")

    for filepath in all_files:
        relative = str(filepath.relative_to(project_root))
        content  = read_file_content(filepath)
        lang     = _detect_language(filepath.suffix)
        size     = filepath.stat().st_size

        files_metadata.append({
            "relative_path": relative,
            "absolute_path": str(filepath),
            "language":      lang,
            "size_bytes":    size,
        })
        logger.debug(f"  Indexing: {relative} ({lang})")

        # Chunk the file and add to RAG
        lines = content.splitlines()
        chunk_size = 60
        for i in range(0, len(lines), chunk_size):
            chunk = "\n".join(lines[i:i+chunk_size])
            if not chunk.strip():
                continue
            
            chunk_id = f"{relative}::chunk_{i//chunk_size}"
            
            # generate embedding
            try:
                emb = get_embedding(chunk)
                collection.add(
                    embeddings=[emb],
                    documents=[chunk],
                    metadatas=[{"file": relative, "language": lang}],
                    ids=[chunk_id]
                )
            except Exception as e:
                logger.warning(f"Failed to embed chunk {chunk_id}: {e}")

    # Build a compact file listing for the summary prompt
    file_listing = "\n".join(
        f"  - {f['relative_path']} ({f['language']}, {f['size_bytes']}B)"
        for f in files_metadata
    )

    summary_prompt = f"""You are a senior software engineer reviewing a codebase.
Below is a list of source files in a project:

{file_listing}

Based ONLY on these filenames and languages, write a concise 1-2 paragraph summary 
guessing what this project does and its main components.
Be factual. Do not mention testing yet."""

    logger.info("  Asking LLM for high-level project summary...")
    print("  [LLM] Generating high-level project summary ", end="")
    try:
        summary = generate(summary_prompt)
    except Exception as e:
        logger.warning(f"  LLM summary failed: {e} — using fallback")
        summary = f"Project at {project_root} with {len(files_metadata)} source files. LLM summary unavailable."

    context = {
        "project_root": str(project_root),
        "total_files":  len(files_metadata),
        "files":        files_metadata, # Note: content is no longer stored here
        "summary":      summary.strip(),
    }

    save_json(context, config.CONTEXT_FILE)
    logger.info(f"  Context saved → {config.CONTEXT_FILE} & ChromaDB")
    return context


def _detect_language(extension: str) -> str:
    """Map a file extension to a human-readable language name."""
    mapping = {
        ".py":   "python",
        ".js":   "javascript",
        ".ts":   "typescript",
        ".jsx":  "jsx",
        ".tsx":  "tsx",
        ".java": "java",
        ".go":   "go",
        ".rb":   "ruby",
        ".php":  "php",
        ".cs":   "csharp",
    }
    return mapping.get(extension.lower(), "text")
