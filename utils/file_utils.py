"""
utils/file_utils.py — File system helpers for the regression testing pipeline.
"""

import os
import json
import logging
from pathlib import Path
from typing import Iterator

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def iter_source_files(root: Path) -> Iterator[Path]:
    """
    Recursively yield source files under `root`, honouring
    EXCLUDED_DIRS, EXCLUDED_FILES, and SUPPORTED_EXTENSIONS from config.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place so os.walk won't descend into them
        dirnames[:] = [
            d for d in dirnames
            if d not in config.EXCLUDED_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if filepath.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
                continue
            if filename in config.EXCLUDED_FILES:
                continue
            # Skip hidden files
            if filename.startswith("."):
                continue
            yield filepath


def read_file_content(filepath: Path, max_lines: int = config.MAX_LINES_PER_FILE) -> str:
    """
    Read up to `max_lines` lines from a text file.
    Returns the content as a string (or an error message on failure).
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            content = "".join(lines[:max_lines])
            content += f"\n\n# ... (truncated at {max_lines} lines of {len(lines)} total)"
        else:
            content = "".join(lines)
        return content
    except Exception as e:
        logger.warning(f"Could not read {filepath}: {e}")
        return f"# ERROR reading file: {e}"


def ensure_output_dirs() -> None:
    """Create all required output directories (Python, JS, Go, Java)."""
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.GENERATED_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    config.GENERATED_TESTS_JS_DIR.mkdir(parents=True, exist_ok=True)
    config.GENERATED_TESTS_GO_DIR.mkdir(parents=True, exist_ok=True)
    config.GENERATED_TESTS_JAVA_DIR.mkdir(parents=True, exist_ok=True)


def save_json(data: dict | list, path: Path) -> None:
    """Serialize `data` to a JSON file with pretty formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.debug(f"Saved JSON → {path}")


def load_json(path: Path) -> dict | list:
    """Load and return a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_test_filename(source_relative_path: str) -> str:
    """
    Convert a relative source path to a pytest-friendly test filename.
    e.g. "src/utils/math.py" → "test_src_utils_math_py.py"
    """
    clean = source_relative_path.replace("/", "_").replace("\\", "_").replace(".", "_")
    return f"test_{clean}.py"


def sanitize_test_filename_for_lang(source_relative_path: str, language: str) -> str:
    """
    Return the appropriate test filename for a given source file and language.

    Convention:
      - python      → test_<stem>.py          (pytest)
      - javascript  → <stem>.test.js          (Jest)
      - go          → <stem>_test.go          (go test)
      - java        → <PascalStem>Test.java   (JUnit 5)

    e.g.
      calculator.js  → calculator.test.js
      calculator.go  → calculator_test.go
      Calculator.java → CalculatorTest.java
    """
    from pathlib import Path as _Path
    p = _Path(source_relative_path)
    stem = p.stem   # filename without extension, e.g. "calculator"

    if language == "python":
        clean = source_relative_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        return f"test_{clean}.py"
    elif language == "javascript":
        return f"{stem}.test.js"
    elif language == "go":
        return f"{stem}_test.go"
    elif language == "java":
        # Capitalise first letter so the class name is valid Java
        pascal_stem = stem[0].upper() + stem[1:] if stem else stem
        return f"{pascal_stem}Test.java"
    else:
        # Generic fallback — treat as plain text
        clean = source_relative_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        return f"test_{clean}.txt"
