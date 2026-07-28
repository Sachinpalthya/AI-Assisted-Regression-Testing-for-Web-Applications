"""
config.py — Central configuration for the AI Regression Testing Framework.
Modify OLLAMA_MODEL to match whichever model you have pulled locally.
"""

import os
from pathlib import Path

# ─── Ollama Settings ────────────────────────────────────────────────────────
OLLAMA_MODEL = "phi3"          # Change to: llama3, mistral, deepseek-coder, etc.
OLLAMA_EMBED_MODEL = "embeddinggemma"    # Using the same model for embeddings as per user request
OLLAMA_HOST  = "http://localhost:11434"
OLLAMA_TIMEOUT = 300                 # seconds — increase for slow machines

# ─── Source File Extensions to Include ──────────────────────────────────────
SUPPORTED_EXTENSIONS = {
    ".py", ".js",  ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rb", ".php", ".cs",
}

# Extensions / dirs to always skip
EXCLUDED_DIRS = {
    "__pycache__", ".git", ".svn", "node_modules",
    ".venv", "venv", "env", ".env",
    "dist", "build", ".mypy_cache", ".pytest_cache",
    "migrations", ".tox", "coverage",
}

EXCLUDED_FILES = {
    "setup.py", "conftest.py", "manage.py",
    "wsgi.py", "asgi.py", "settings.py",
}

# Max lines to include per file in context (to stay within token limits)
MAX_LINES_PER_FILE = 400

# ─── Output Paths ───────────────────────────────────────────────────────────
OUTPUT_DIR             = Path("output")
CONTEXT_FILE           = OUTPUT_DIR / "context.json"
CHROMA_DB_DIR          = OUTPUT_DIR / "chroma_db"
TESTABLE_FILES_FILE    = OUTPUT_DIR / "testable_files.json"
GENERATED_TESTS_DIR    = OUTPUT_DIR / "generated_tests"
GENERATED_TESTS_JS_DIR  = OUTPUT_DIR / "generated_tests" / "js"
GENERATED_TESTS_GO_DIR  = OUTPUT_DIR / "generated_tests" / "go"
GENERATED_TESTS_JAVA_DIR = OUTPUT_DIR / "generated_tests" / "java"
PYTEST_RAW_FILE        = OUTPUT_DIR / "pytest_raw.txt"
PYTEST_JSON_FILE       = OUTPUT_DIR / "pytest_report.json"
ANALYSIS_REPORT_FILE   = OUTPUT_DIR / "analysis_report.json"
HTML_REPORT_FILE       = OUTPUT_DIR / "report.html"

def set_project_path(project_path: Path):
    """
    Dynamically update all output path globals to be relative to the analyzed project path.
    """
    global OUTPUT_DIR, CONTEXT_FILE, CHROMA_DB_DIR, TESTABLE_FILES_FILE, GENERATED_TESTS_DIR
    global GENERATED_TESTS_JS_DIR, GENERATED_TESTS_GO_DIR, GENERATED_TESTS_JAVA_DIR
    global PYTEST_RAW_FILE, PYTEST_JSON_FILE, ANALYSIS_REPORT_FILE, HTML_REPORT_FILE

    OUTPUT_DIR              = project_path / "output"
    CONTEXT_FILE            = OUTPUT_DIR / "context.json"
    CHROMA_DB_DIR           = OUTPUT_DIR / "chroma_db"
    TESTABLE_FILES_FILE     = OUTPUT_DIR / "testable_files.json"
    GENERATED_TESTS_DIR     = OUTPUT_DIR / "generated_tests"
    GENERATED_TESTS_JS_DIR  = OUTPUT_DIR / "generated_tests" / "js"
    GENERATED_TESTS_GO_DIR  = OUTPUT_DIR / "generated_tests" / "go"
    GENERATED_TESTS_JAVA_DIR = OUTPUT_DIR / "generated_tests" / "java"
    PYTEST_RAW_FILE         = OUTPUT_DIR / "pytest_raw.txt"
    PYTEST_JSON_FILE        = OUTPUT_DIR / "pytest_report.json"
    ANALYSIS_REPORT_FILE    = OUTPUT_DIR / "analysis_report.json"
    HTML_REPORT_FILE        = OUTPUT_DIR / "report.html"

# ─── Pytest Settings ────────────────────────────────────────────────────────
PYTEST_TIMEOUT = 120    # seconds for entire test suite run

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"      # DEBUG | INFO | WARNING | ERROR
