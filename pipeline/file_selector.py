"""
pipeline/file_selector.py — Stage 2: LLM-Based Testable File Selector

Sends the codebase context to the LLM and asks it to return a JSON list
of source files that contain meaningful testable logic (functions, classes,
methods, business rules). Configuration files, entry-points and boilerplate
are excluded.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from utils.file_utils import save_json
from utils.ollama_client import generate

logger = logging.getLogger(__name__)


def select_testable_files(context: dict[str, Any]) -> list[dict]:
    """
    Stage 2 entry point.

    Given the codebase context produced by Stage 1, asks the LLM which
    files should be tested and returns a list of file dicts.

    Returns:
        List of file dicts (subset of context["files"]) that should be tested.
    """
    logger.info("[Stage 2] Selecting testable files via LLM...")

    file_list_text = "\n".join(
        f"  {i+1}. {f['relative_path']} ({f['language']}, {f['size_bytes']}B)"
        for i, f in enumerate(context["files"])
    )

    prompt = f"""You are a QA engineer reviewing a codebase.

Project summary:
{context.get('summary', 'No summary available.')}

Source files in the project:
{file_list_text}

Your task: Identify which files contain TESTABLE business logic.

Include files that contain:
- Functions or methods with clear inputs/outputs
- Class definitions with meaningful behaviour
- Business rules, calculations, validations
- Error handling logic
- Data transformation or processing logic

Exclude files that are:
- Configuration files (settings, constants, config)
- Entry points that only start a server (main.py with only __main__ guard)
- Migration files
- Pure data files (no logic)
- Test files themselves

Return your answer as a valid JSON array of relative file paths only.
Do not include any explanation — ONLY the JSON array.

Example output format:
["src/calculator.py", "src/user_manager.py", "utils/string_helper.py"]

Your answer:"""

    logger.info("  Asking LLM to select testable files (streaming)...")
    print("  [LLM] Selecting testable files ", end="")

    try:
        response = generate(prompt)
        testable_paths = _parse_json_list(response)
    except Exception as e:
        logger.warning(f"  LLM file selection failed: {e} — defaulting to all Python files")
        testable_paths = [
            f["relative_path"]
            for f in context["files"]
            if f["language"] == "python"
        ]

    # Resolve to full file dicts from context
    file_map = {f["relative_path"]: f for f in context["files"]}
    selected = []
    for path in testable_paths:
        if path in file_map:
            selected.append(file_map[path])
        else:
            logger.warning(f"  LLM selected unknown path: '{path}' — skipping")

    # Fallback: if LLM returned nothing valid, include all source files
    if not selected:
        logger.warning("  No valid files selected by LLM — falling back to all files")
        selected = context["files"]

    logger.info(f"  Selected {len(selected)} file(s) for test generation")
    for f in selected:
        logger.info(f"    ✓ {f['relative_path']}")

    save_json(
        {"testable_files": [f["relative_path"] for f in selected]},
        config.TESTABLE_FILES_FILE
    )
    return selected


def _parse_json_list(response: str) -> list[str]:
    """
    Extract a JSON array from the LLM response, handling cases where
    the model wraps the JSON in markdown code fences.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", response, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()

    # Try to find the first [...] block
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try parsing the full cleaned text
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        pass

    # Last resort: extract quoted strings that look like file paths
    paths = re.findall(r'"([^"]+\.[a-z]+)"', text)
    return paths
