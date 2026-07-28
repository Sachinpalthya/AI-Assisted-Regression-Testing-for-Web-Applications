"""
pipeline/report_analyzer.py — Stage 5: LLM Failure Analyzer

Takes the pytest run results and asks the LLM to:
  1. Identify the root cause of each failure
  2. Map failures to source files
  3. Assign severity (high / medium / low)
  4. Provide a plain-English explanation

Output: structured analysis_report.json
"""

import json
import logging
import re
from typing import Any

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from utils.file_utils import save_json
from utils.ollama_client import generate

logger = logging.getLogger(__name__)


def analyze_results(test_results: dict[str, Any], context: dict[str, Any]) -> dict:
    """
    Stage 5 entry point.

    Sends failed tests to the LLM for root-cause analysis.

    Args:
        test_results: Output from Stage 4 (test_runner)
        context:      Codebase context from Stage 1

    Returns:
        analysis dict saved to output/analysis_report.json
    """
    summary  = test_results.get("summary", {})
    all_tests = test_results.get("tests", [])
    failures = [t for t in all_tests if t.get("outcome") in ("failed", "error")]

    logger.info(f"[Stage 5] Analyzing {len(failures)} failure(s) from {summary.get('total', 0)} test(s)")

    analyzed_failures = []

    if not failures:
        logger.info("  No failures — nothing to analyze")
        analysis = _build_analysis(summary, [], test_results.get("raw_output", ""))
        save_json(analysis, config.ANALYSIS_REPORT_FILE)
        return analysis

    # Build a compact failure report text for the LLM
    failure_text = _format_failures_for_llm(failures)

    # Get relevant source code snippets for context
    source_snippets = _get_relevant_sources(failures, context)

    prompt = f"""You are a senior software engineer analyzing test failures.

Project summary:
{context.get('summary', '')[:500]}

Test failure report:
{failure_text}

Relevant source code:
{source_snippets}

For each failing test above, provide a structured JSON analysis.
Return a JSON array where each element has these exact keys:
  - "test_name"    : exact test function name from the failure report
  - "source_file"  : the most likely source file that contains the buggy code
  - "root_cause"   : a clear, technical 1-2 sentence explanation of why the test fails
  - "severity"     : "high" | "medium" | "low"
  - "suggestion"   : a brief (2-4 line) code snippet or description of the fix

Return ONLY the JSON array, no other text.

Example format:
[
  {{
    "test_name": "test_divide_by_zero",
    "source_file": "calculator.py",
    "root_cause": "The divide function does not handle division by zero, raising an unhandled ZeroDivisionError.",
    "severity": "high",
    "suggestion": "Add a guard: if b == 0: raise ValueError('Cannot divide by zero')"
  }}
]

Your analysis:"""

    logger.info("  Asking LLM to analyze failures (streaming)...")
    print("\n  [LLM] Analyzing test failures ", end="")

    try:
        response = generate(prompt)
        analyzed_failures = _parse_json_analysis(response, failures)
    except Exception as e:
        logger.warning(f"  LLM analysis failed: {e} — using basic analysis")
        analyzed_failures = _basic_fallback_analysis(failures)

    analysis = _build_analysis(summary, analyzed_failures, test_results.get("raw_output", ""))
    save_json(analysis, config.ANALYSIS_REPORT_FILE)
    logger.info(f"  Analysis saved → {config.ANALYSIS_REPORT_FILE}")
    return analysis


def _format_failures_for_llm(failures: list[dict]) -> str:
    """Format failing tests into a readable text block for the LLM."""
    lines = []
    for i, t in enumerate(failures, 1):
        lines.append(f"\n--- Failure {i}: {t.get('name', 'unknown')} ---")
        lines.append(f"Node ID : {t.get('node_id', '')}")
        lines.append(f"Outcome : {t.get('outcome', '')}")
        if t.get("error"):
            lines.append(f"Error   :\n{t['error'][:500]}")
    return "\n".join(lines)


def _get_relevant_sources(failures: list[dict], context: dict) -> str:
    """
    Find source code snippets related to the failing tests
    by matching test names to source files in context.
    """
    from pathlib import Path
    from utils.file_utils import read_file_content
    project_root = Path(context.get("project_root", "."))
    snippets = []
    seen = set()

    for failure in failures[:5]:   # cap at 5 to avoid huge prompts
        source = failure.get("source_file", "")
        # Try to find matching source file
        for f_info in context.get("files", []):
            path = f_info.get("relative_path", "")
            if source and source.replace(".py", "") in path and path not in seen:
                absolute_path = project_root / path
                if absolute_path.exists():
                    content = read_file_content(absolute_path)
                    snippet = "\n".join(content.splitlines()[:80])
                    snippets.append(f"\n=== {path} ===\n{snippet}")
                    seen.add(path)
                break

    return "\n".join(snippets) if snippets else "(source code not matched)"


def _parse_json_analysis(response: str, failures: list[dict]) -> list[dict]:
    """Parse the LLM's JSON array response for failure analysis."""
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", response, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text).strip()

    # Find first [...] block
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return _normalize_failures(data, failures)
        except json.JSONDecodeError:
            pass

    # Try full text
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return _normalize_failures(data, failures)
    except json.JSONDecodeError:
        pass

    return _basic_fallback_analysis(failures)


def _normalize_failures(raw: list, fallback_failures: list[dict]) -> list[dict]:
    """Ensure each analysis entry has the required keys."""
    normalized = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "test_name":   item.get("test_name", "unknown"),
            "source_file": item.get("source_file", "unknown"),
            "root_cause":  item.get("root_cause", "Root cause not identified"),
            "severity":    item.get("severity", "medium").lower(),
            "suggestion":  item.get("suggestion", ""),
        })
    return normalized


def _basic_fallback_analysis(failures: list[dict]) -> list[dict]:
    """Generate a basic analysis when LLM fails."""
    return [
        {
            "test_name":   t.get("name", "unknown"),
            "source_file": t.get("source_file", "unknown"),
            "root_cause":  f"Test failed with: {t.get('error', 'unknown error')[:200]}",
            "severity":    "medium",
            "suggestion":  "Review the source function for incorrect logic or missing error handling.",
        }
        for t in failures
    ]


def _build_analysis(summary: dict, failures: list, raw_output: str) -> dict:
    """Build the final analysis report structure."""
    total  = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    errors = summary.get("errors", 0)
    pass_rate = round((passed / total * 100) if total > 0 else 0, 1)

    return {
        "total_tests": total,
        "passed":      passed,
        "failed":      failed,
        "errors":      errors,
        "pass_rate":   pass_rate,
        "failures":    failures,
        "raw_output_path": str(config.PYTEST_RAW_FILE),
    }
