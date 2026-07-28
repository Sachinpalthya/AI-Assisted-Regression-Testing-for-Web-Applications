"""
pipeline/test_generator.py — Stage 3: LLM-Based Test Generator

For each file selected in Stage 2, fetches RAG context, asks the LLM to
generate a test plan (JSON), then generates up to 4 test cases.
Supports Python (pytest), JavaScript (Jest), Go (go test), and Java (JUnit 5).
Tests are saved to:
  - output/generated_tests/           (Python .py)
  - output/generated_tests/js/        (JavaScript .test.js)
  - output/generated_tests/go/        (Go _test.go)
  - output/generated_tests/java/      (Java *Test.java)
"""

import logging
import re
import ast
import json
from pathlib import Path
from typing import Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from utils.file_utils import (
    sanitize_test_filename,
    sanitize_test_filename_for_lang,
    ensure_output_dirs,
    read_file_content,
)
from utils.ollama_client import generate, get_embedding

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger(__name__)

# ── Supported languages ───────────────────────────────────────────────────────
SUPPORTED_LANGUAGES = {"python", "javascript", "go", "java"}

# ── Step 1: JSON Test Plan — language-agnostic ────────────────────────────────
TEST_PLAN_PROMPT = """You are an expert QA engineer.
Review the following source code and generate a JSON list of strings describing the test cases needed.
Keep it strictly to a maximum of 4 essential test cases to fit within a small model's capacity.

Source file: {relative_path}
Language: {language}
Context: {rag_context}

=== SOURCE CODE ===
{source_code}
=== END SOURCE CODE ===

Output ONLY a valid JSON array of strings. Do not include markdown fences, do not explain.
Example:
["Test happy path for calculate_total", "Test boundary condition with zero", "Test edge case with negative values"]

Respond with JSON array:"""

# ── Step 2a: Python / pytest ──────────────────────────────────────────────────
PYTHON_TEST_CODE_PROMPT = """You are an expert Python QA engineer.
Write a pytest file for the following source code.
Implement ONLY the following test cases:
{test_plan}

Source file: {relative_path}
Context: {rag_context}

=== SOURCE CODE ===
{source_code}
=== END SOURCE CODE ===

Requirements:
1. Use pytest
2. Import correctly: from {module_import} import ...
3. Write ONLY the test cases requested.
4. Output ONLY valid Python code — no markdown fences, no text outside comments.

Begin Python code:"""

# ── Step 2b: JavaScript / Jest ────────────────────────────────────────────────
JS_TEST_CODE_PROMPT = """You are an expert JavaScript QA engineer.
Write a Jest test file for the following source code.
Implement ONLY the following test cases:
{test_plan}

Source file: {relative_path}
Context: {rag_context}

=== SOURCE CODE ===
{source_code}
=== END SOURCE CODE ===

Requirements:
1. Use Jest (describe / it / expect).
2. Use CommonJS require: const {{ ... }} = require('./{module_name}');
   - Use relative path with './' prefix so Jest can resolve it.
3. Write ONLY the test cases requested.
4. Output ONLY valid JavaScript — no markdown fences, no explanations.
5. Do NOT use import/export (use require/module.exports).
6. Handle async functions with async/await if necessary.

Begin JavaScript code:"""

# ── Step 2c: Go / go test ─────────────────────────────────────────────────────
GO_TEST_CODE_PROMPT = """You are an expert Go QA engineer.
Write a Go test file for the following source code.
Implement ONLY the following test cases:
{test_plan}

Source file: {relative_path}
Package name: {package_name}
Context: {rag_context}

=== SOURCE CODE ===
{source_code}
=== END SOURCE CODE ===

Requirements:
1. Use the standard "testing" package (import "testing").
2. Package declaration must be: package {package_name}
3. Each test function must be named TestXxx(t *testing.T).
4. Use t.Errorf or t.Fatalf to report failures.
5. Write ONLY the test cases requested.
6. Output ONLY valid Go code — no markdown fences, no explanations.

Begin Go code:"""

# ── Step 2d: Java / JUnit 5 ───────────────────────────────────────────────────
JAVA_TEST_CODE_PROMPT = """You are an expert Java QA engineer.
Write a JUnit 5 test class for the following source code.
Implement ONLY the following test cases:
{test_plan}

Source file: {relative_path}
Class name: {class_name}
Context: {rag_context}

=== SOURCE CODE ===
{source_code}
=== END SOURCE CODE ===

Requirements:
1. Use JUnit 5 annotations: @Test, @BeforeEach etc. from org.junit.jupiter.api.*.
2. The test class must be named {class_name}Test.
3. Import the class under test correctly (assume same package / default package).
4. Use Assertions.assertEquals, Assertions.assertThrows, etc.
5. Write ONLY the test cases requested.
6. Output ONLY valid Java code — no markdown fences, no explanations.
7. Do NOT include a package declaration (use default package for simplicity).

Begin Java code:"""

# ── Syntax correction (Python only — other langs rely on runtime) ──────────────
PYTHON_SYNTAX_CORRECTION_PROMPT = """The following Python test code has a syntax error:
{error_message}

=== BROKEN CODE ===
{broken_code}
=== END BROKEN CODE ===

Fix the syntax error and output the entire corrected Python file.
Output ONLY valid Python code — no markdown fences."""


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_tests(
    selected_files: list[dict],
    project_summary: str,
    project_root: Path,
) -> list[dict]:
    ensure_output_dirs()
    results = []
    total = len(selected_files)

    chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR)) if chromadb else None
    collection = None
    if chroma_client:
        try:
            collection = chroma_client.get_collection("project_context")
        except Exception as e:
            logger.warning(f"Could not load RAG collection: {e}")

    for idx, file_info in enumerate(selected_files, 1):
        relative_path = file_info["relative_path"]
        language      = file_info["language"]

        # Skip truly unsupported languages
        if language not in SUPPORTED_LANGUAGES:
            logger.info(f"  [{idx}/{total}] Skipping unsupported language '{language}': {relative_path}")
            results.append({
                "source_file": relative_path,
                "test_file":   None,
                "status":      "skipped",
                "reason":      f"Language '{language}' not supported (supported: {', '.join(sorted(SUPPORTED_LANGUAGES))})",
            })
            continue

        # Read source code
        absolute_path = project_root / relative_path
        if not absolute_path.exists():
            logger.warning(f"  [{idx}/{total}] Source file not found: {absolute_path}")
            continue
        source_code = read_file_content(absolute_path)

        logger.info(f"  [{idx}/{total}] Generating {language} tests for: {relative_path}")
        print(f"\n  [LLM] Generating {language} tests for {relative_path} ", end="")

        # 1. Fetch RAG Context
        rag_context = "No additional context."
        if collection:
            try:
                emb = get_embedding(source_code[:500])
                rag_results = collection.query(query_embeddings=[emb], n_results=3)
                docs  = rag_results.get("documents", [[]])[0]
                metas = rag_results.get("metadatas", [[]])[0]
                external_docs = [
                    d for d, m in zip(docs, metas)
                    if m.get("file") != relative_path
                ]
                if external_docs:
                    rag_context = "\n...\n".join(external_docs[:2])
            except Exception as e:
                logger.debug(f"RAG query failed: {e}")

        try:
            # Step 1: Test Plan (language-agnostic)
            plan_prompt = TEST_PLAN_PROMPT.format(
                relative_path=relative_path,
                language=language,
                rag_context=rag_context,
                source_code=source_code,
            )
            raw_plan  = generate(plan_prompt)
            test_plan = _extract_json_array(raw_plan)
            test_plan_str = json.dumps(test_plan[:4], indent=2)
            logger.info(f"    Planned {len(test_plan[:4])} tests.")

            # Step 2: Language-specific code generation
            test_code, test_filename, test_dir = _generate_for_language(
                language, relative_path, source_code, rag_context, test_plan_str
            )

            # Step 3: Save file
            test_filepath = test_dir / test_filename
            with open(test_filepath, "w", encoding="utf-8") as f:
                f.write(_make_file_header(relative_path, language))
                f.write(test_code)

            logger.info(f"    ✓ Saved → {test_filepath}")
            results.append({
                "source_file": relative_path,
                "test_file":   str(test_filepath),
                "language":    language,
                "status":      "ok",
                "error":       None,
            })

        except Exception as e:
            logger.error(f"    ✗ Test generation failed for {relative_path}: {e}")
            results.append({
                "source_file": relative_path,
                "test_file":   None,
                "language":    language,
                "status":      "failed",
                "error":       str(e),
            })

    success = sum(1 for r in results if r["status"] == "ok")
    logger.info(f"\n[Stage 3] Generated tests for {success}/{total} file(s)")
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Per-language code generation
# ─────────────────────────────────────────────────────────────────────────────

def _generate_for_language(
    language: str,
    relative_path: str,
    source_code: str,
    rag_context: str,
    test_plan_str: str,
) -> tuple[str, str, Path]:
    """
    Generate test code for the given language.

    Returns:
        (test_code: str, test_filename: str, test_dir: Path)
    """
    if language == "python":
        return _gen_python(relative_path, source_code, rag_context, test_plan_str)
    elif language == "javascript":
        return _gen_javascript(relative_path, source_code, rag_context, test_plan_str)
    elif language == "go":
        return _gen_go(relative_path, source_code, rag_context, test_plan_str)
    elif language == "java":
        return _gen_java(relative_path, source_code, rag_context, test_plan_str)
    else:
        raise ValueError(f"Unsupported language: {language}")


def _gen_python(relative_path, source_code, rag_context, test_plan_str):
    module_import = _path_to_module(relative_path)
    prompt = PYTHON_TEST_CODE_PROMPT.format(
        test_plan=test_plan_str,
        relative_path=relative_path,
        rag_context=rag_context,
        source_code=source_code,
        module_import=module_import,
    )
    raw_code  = generate(prompt)
    test_code = _clean_code_response(raw_code)
    test_code = _ensure_python_syntax_valid(test_code)

    test_filename = sanitize_test_filename_for_lang(relative_path, "python")
    return test_code, test_filename, config.GENERATED_TESTS_DIR


def _gen_javascript(relative_path, source_code, rag_context, test_plan_str):
    from pathlib import Path as _Path
    stem = _Path(relative_path).stem
    # The require path is the stem (Jest will be run from generated_tests/js dir,
    # and we'll point it at the project root via moduleDirectories / roots)
    prompt = JS_TEST_CODE_PROMPT.format(
        test_plan=test_plan_str,
        relative_path=relative_path,
        rag_context=rag_context,
        source_code=source_code,
        module_name=stem,
    )
    raw_code  = generate(prompt)
    test_code = _clean_js_response(raw_code)

    test_filename = sanitize_test_filename_for_lang(relative_path, "javascript")
    return test_code, test_filename, config.GENERATED_TESTS_JS_DIR


def _gen_go(relative_path, source_code, rag_context, test_plan_str):
    # Infer package name from source code (first "^package X" line)
    package_name = _detect_go_package(source_code) or "main"
    prompt = GO_TEST_CODE_PROMPT.format(
        test_plan=test_plan_str,
        relative_path=relative_path,
        rag_context=rag_context,
        source_code=source_code,
        package_name=package_name,
    )
    raw_code  = generate(prompt)
    test_code = _clean_go_response(raw_code)

    test_filename = sanitize_test_filename_for_lang(relative_path, "go")
    return test_code, test_filename, config.GENERATED_TESTS_GO_DIR


def _gen_java(relative_path, source_code, rag_context, test_plan_str):
    from pathlib import Path as _Path
    stem = _Path(relative_path).stem
    class_name = stem[0].upper() + stem[1:] if stem else stem   # PascalCase

    prompt = JAVA_TEST_CODE_PROMPT.format(
        test_plan=test_plan_str,
        relative_path=relative_path,
        rag_context=rag_context,
        source_code=source_code,
        class_name=class_name,
    )
    raw_code  = generate(prompt)
    test_code = _clean_java_response(raw_code)

    test_filename = sanitize_test_filename_for_lang(relative_path, "java")
    return test_code, test_filename, config.GENERATED_TESTS_JAVA_DIR


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_json_array(text: str) -> list[str]:
    """Attempt to extract a JSON array from the text, falling back to basic parsing."""
    try:
        start = text.find('[')
        end   = text.rfind(']')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
    except Exception:
        pass
    return [line.strip("- *") for line in text.splitlines() if line.strip()][:4]


def _ensure_python_syntax_valid(code: str, retries: int = 2) -> str:
    """Validate Python code syntax using ast. Ask LLM to fix if broken."""
    current_code = code
    for attempt in range(retries):
        try:
            ast.parse(current_code)
            return current_code
        except SyntaxError as e:
            logger.warning(f"    SyntaxError detected (attempt {attempt+1}/{retries}): {e}")
            fix_prompt = PYTHON_SYNTAX_CORRECTION_PROMPT.format(
                error_message=str(e),
                broken_code=current_code,
            )
            raw_fix      = generate(fix_prompt)
            current_code = _clean_code_response(raw_fix)
    return current_code


def _path_to_module(relative_path: str) -> str:
    path = relative_path.replace("\\", "/")
    if path.endswith(".py"):
        path = path[:-3]
    return path.replace("/", ".")


def _detect_go_package(source_code: str) -> str | None:
    """Extract Go package name from 'package <name>' declaration."""
    m = re.search(r"^\s*package\s+(\w+)", source_code, re.MULTILINE)
    return m.group(1) if m else None


# ── Code cleaners ─────────────────────────────────────────────────────────────

def _clean_code_response(response: str) -> str:
    """Strip markdown fences and leading prose from Python code responses."""
    code = re.sub(r"```python\s*", "", response, flags=re.IGNORECASE)
    code = re.sub(r"```\s*", "", code)
    code = code.strip()

    lines = code.splitlines()
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ", "def ", "class ", "#", "@", '"""', "'''")):
            start_idx = i
            break
    return "\n".join(lines[start_idx:]).strip() + "\n"


def _clean_js_response(response: str) -> str:
    """Strip markdown fences from JavaScript responses."""
    code = re.sub(r"```(?:javascript|js)?\s*", "", response, flags=re.IGNORECASE)
    code = re.sub(r"```\s*", "", code)
    return code.strip() + "\n"


def _clean_go_response(response: str) -> str:
    """Strip markdown fences from Go responses."""
    code = re.sub(r"```(?:go|golang)?\s*", "", response, flags=re.IGNORECASE)
    code = re.sub(r"```\s*", "", code)
    return code.strip() + "\n"


def _clean_java_response(response: str) -> str:
    """Strip markdown fences from Java responses."""
    code = re.sub(r"```(?:java)?\s*", "", response, flags=re.IGNORECASE)
    code = re.sub(r"```\s*", "", code)
    return code.strip() + "\n"


def _make_file_header(source_file: str, language: str = "python") -> str:
    comment_styles = {
        "python":     ("# ", ""),
        "javascript": ("// ", ""),
        "go":         ("// ", ""),
        "java":       ("// ", ""),
    }
    prefix, _ = comment_styles.get(language, ("# ", ""))

    lines = [
        f"{prefix}AI-Generated Regression Tests",
        f"{prefix}Source: {source_file}",
        f"{prefix}Generated by: AI Regression Testing Framework (Ollama RAG Optimised)",
        f"{prefix}Framework: {'pytest' if language == 'python' else 'Jest' if language == 'javascript' else 'go test' if language == 'go' else 'JUnit 5'}",
        "",
    ]
    return "\n".join(lines) + "\n"
