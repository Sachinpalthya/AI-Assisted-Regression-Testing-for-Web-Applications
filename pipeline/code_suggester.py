"""
pipeline/code_suggester.py — Stage 6: LLM Code Improvement Suggester

For each source file that had failing tests, asks the LLM to:
  1. Review the source code in light of the failures
  2. Provide specific, minimal code changes as before/after diffs
  3. Explain why each change is needed

Results are appended to analysis_report.json and rendered in report.html.
"""

import logging
import re
from pathlib import Path
from typing import Any

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from utils.file_utils import save_json, load_json
from utils.ollama_client import generate

logger = logging.getLogger(__name__)


def suggest_code_fixes(
    analysis: dict[str, Any],
    context:  dict[str, Any],
) -> list[dict]:
    """
    Stage 6 entry point.

    For each source file mentioned in failures, asks the LLM to suggest
    concrete code improvements.

    Returns:
        List of suggestion dicts:
        [{"source_file": str, "suggestion_text": str}, ...]
    """
    failures = analysis.get("failures", [])
    if not failures:
        logger.info("[Stage 6] No failures to fix — skipping code suggestions")
        return []

    logger.info(f"[Stage 6] Generating code fix suggestions for {len(failures)} failure(s)...")

    # Group failures by source file to avoid duplicating work
    by_source: dict[str, list[dict]] = {}
    for f in failures:
        src = f.get("source_file", "unknown")
        by_source.setdefault(src, []).append(f)

    # Build a source file content lookup dynamically
    from utils.file_utils import read_file_content
    project_root = Path(context.get("project_root", "."))
    file_content_map = {}
    for f in context.get("files", []):
        rel_path = f.get("relative_path", "")
        abs_path = project_root / rel_path
        if abs_path.exists():
            file_content_map[rel_path] = read_file_content(abs_path)

    suggestions = []

    for source_file, file_failures in by_source.items():
        source_code = _find_source_code(source_file, file_content_map)
        failure_summary = _format_failures(file_failures)

        logger.info(f"  Suggesting fixes for: {source_file}")
        print(f"\n  [LLM] Suggesting fixes for {source_file} ", end="")

        prompt = f"""You are a senior software engineer fixing bugs in production code.

Source file: {source_file}

Test failures related to this file:
{failure_summary}

Source code:
```python
{source_code}
```

Your task:
1. Identify the specific lines/functions in the source code that are causing the test failures
2. Provide concrete, minimal code changes to fix the issues
3. Format each change as a clear BEFORE/AFTER diff with an explanation

Use this format for each fix:
---
ISSUE: [brief description]
BEFORE:
```python
[original code snippet]
```
AFTER:
```python
[corrected code snippet]
```
REASON: [why this fixes the problem]
---

Focus on correctness fixes only. Do not refactor unrelated code.
Begin:"""

        try:
            response = generate(prompt)
            suggestion_text = _clean_suggestion(response)
        except Exception as e:
            logger.warning(f"  LLM suggestion failed for {source_file}: {e}")
            suggestion_text = (
                f"Manual review required for {source_file}.\n"
                f"Failures:\n{failure_summary}"
            )

        suggestions.append({
            "source_file":     source_file,
            "suggestion_text": suggestion_text,
        })

    # Persist suggestions back into analysis report
    try:
        existing = load_json(config.ANALYSIS_REPORT_FILE)
        existing["code_suggestions"] = suggestions
        save_json(existing, config.ANALYSIS_REPORT_FILE)
        logger.info(f"  Code suggestions appended → {config.ANALYSIS_REPORT_FILE}")
    except Exception as e:
        logger.warning(f"  Could not update analysis report: {e}")

    logger.info(f"[Stage 6] Code suggestions generated for {len(suggestions)} file(s)")
    return suggestions


def _find_source_code(source_file: str, file_content_map: dict[str, str]) -> str:
    """Locate source code by fuzzy-matching the source_file name."""
    # Exact match
    if source_file in file_content_map:
        return file_content_map[source_file]

    # Partial match (source_file might be just the basename)
    base = source_file.replace(".py", "").lower()
    for path, content in file_content_map.items():
        if base in path.lower():
            return content

    return "(source code not found — provide code review manually)"


def _format_failures(failures: list[dict]) -> str:
    """Format a list of failures as readable text."""
    lines = []
    for f in failures:
        lines.append(f"• Test: {f.get('test_name', 'unknown')}")
        lines.append(f"  Root cause: {f.get('root_cause', '')}")
        lines.append(f"  Severity: {f.get('severity', 'unknown')}")
        if f.get("suggestion"):
            lines.append(f"  Hint: {f['suggestion']}")
        lines.append("")
    return "\n".join(lines)


def _clean_suggestion(response: str) -> str:
    """Lightly clean the LLM's suggestion text."""
    # Remove excessive blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", response)
    return text.strip()
