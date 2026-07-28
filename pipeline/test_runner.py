"""
pipeline/test_runner.py — Stage 4: Multi-Language Test Runner

Executes generated test files for all supported languages:
  - Python   → pytest
  - JavaScript → Jest (via npx jest)
  - Go         → go test
  - Java       → javac + junit-platform-console-standalone JAR
                 (or Maven if pom.xml is present)

Captures raw output, parses results, and returns a unified structured dict
for downstream analysis.
"""

import json
import logging
import subprocess
import sys
import shutil
import re
import os
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from utils.file_utils import save_json

logger = logging.getLogger(__name__)

# JUnit standalone JAR (downloaded once if missing)
JUNIT_STANDALONE_JAR_URL = (
    "https://repo1.maven.org/maven2/org/junit/platform/"
    "junit-platform-console-standalone/1.10.2/"
    "junit-platform-console-standalone-1.10.2.jar"
)
JUNIT_JAR_PATH = Path(__file__).parent.parent / "lib" / "junit-platform-console-standalone.jar"


# ─────────────────────────────────────────────────────────────────────────────
#  Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_tests(project_root: Path) -> dict[str, Any]:
    """
    Stage 4 entry point.

    Dispatches to each language-specific runner and merges results into a
    single unified report dict.

    Returns:
        {
            "summary": {"total": int, "passed": int, "failed": int, "errors": int},
            "tests":   [...],
            "raw_output": str,
        }
    """
    all_tests:     list[dict] = []
    all_raw_lines: list[str]  = []

    # ── Python (pytest) ───────────────────────────────────────────────────────
    py_result = _run_python_tests(project_root)
    all_tests.extend(py_result.get("tests", []))
    all_raw_lines.append("=== Python (pytest) ===\n" + py_result.get("raw_output", ""))

    # ── JavaScript (Jest) ─────────────────────────────────────────────────────
    js_dir = config.GENERATED_TESTS_JS_DIR
    if js_dir.exists() and any(js_dir.glob("*.test.js")):
        js_result = _run_js_tests(js_dir, project_root)
        all_tests.extend(js_result.get("tests", []))
        all_raw_lines.append("=== JavaScript (Jest) ===\n" + js_result.get("raw_output", ""))
    else:
        logger.info("[Stage 4] No JavaScript test files found — skipping Jest")

    # ── Go (go test) ─────────────────────────────────────────────────────────
    go_dir = config.GENERATED_TESTS_GO_DIR
    if go_dir.exists() and any(go_dir.glob("*_test.go")):
        go_result = _run_go_tests(go_dir, project_root)
        all_tests.extend(go_result.get("tests", []))
        all_raw_lines.append("=== Go (go test) ===\n" + go_result.get("raw_output", ""))
    else:
        logger.info("[Stage 4] No Go test files found — skipping go test")

    # ── Java (JUnit 5) ────────────────────────────────────────────────────────
    java_dir = config.GENERATED_TESTS_JAVA_DIR
    if java_dir.exists() and any(java_dir.glob("*Test.java")):
        java_result = _run_java_tests(java_dir, project_root)
        all_tests.extend(java_result.get("tests", []))
        all_raw_lines.append("=== Java (JUnit 5) ===\n" + java_result.get("raw_output", ""))
    else:
        logger.info("[Stage 4] No Java test files found — skipping JUnit")

    # ── Merge ─────────────────────────────────────────────────────────────────
    raw_output = "\n\n".join(all_raw_lines)
    total  = len(all_tests)
    passed = sum(1 for t in all_tests if t.get("outcome") == "passed")
    failed = sum(1 for t in all_tests if t.get("outcome") == "failed")
    errors = sum(1 for t in all_tests if t.get("outcome") == "error")

    structured = {
        "summary": {
            "total":  total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
        },
        "tests":      all_tests,
        "raw_output": raw_output,
    }

    # Save raw output
    config.PYTEST_RAW_FILE.write_text(raw_output, encoding="utf-8")
    save_json(structured, config.PYTEST_JSON_FILE)

    logger.info(
        f"[Stage 4] Combined results: "
        f"{passed} passed, {failed} failed, {errors} errors"
    )
    return structured


# ─────────────────────────────────────────────────────────────────────────────
#  Python runner (pytest)
# ─────────────────────────────────────────────────────────────────────────────

def _run_python_tests(project_root: Path) -> dict:
    """Run pytest on output/generated_tests/ (Python files only)."""
    test_dir = config.GENERATED_TESTS_DIR

    if not test_dir.exists() or not any(test_dir.glob("test_*.py")):
        logger.warning("[Stage 4] No Python test files found — skipping pytest")
        return _empty_result("No Python test files found")

    logger.info(f"[Stage 4] Running pytest on: {test_dir}")

    cmd = [
        sys.executable, "-m", "pytest",
        str(project_root),
        "--tb=short",
        "-v",
        "--no-header",
        "--json-report",
        f"--json-report-file={config.PYTEST_JSON_FILE.resolve()}",
        "--json-report-indent=2",
        "-p", "no:cacheprovider",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=config.PYTEST_TIMEOUT,
        )
        raw_output = result.stdout + result.stderr

        if config.PYTEST_JSON_FILE.exists():
            return _parse_pytest_json_report(config.PYTEST_JSON_FILE, raw_output)
        return _parse_stdout_fallback(raw_output, language="python")

    except subprocess.TimeoutExpired:
        msg = f"pytest timed out after {config.PYTEST_TIMEOUT}s"
        logger.error(f"[Stage 4] {msg}")
        return _empty_result(msg)
    except FileNotFoundError:
        msg = "pytest not found — install with: pip install pytest pytest-json-report"
        logger.error(f"[Stage 4] {msg}")
        return _empty_result(msg)
    except Exception as e:
        logger.error(f"[Stage 4] Python runner error: {e}")
        return _empty_result(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  JavaScript runner (Jest)
# ─────────────────────────────────────────────────────────────────────────────

def _run_js_tests(js_test_dir: Path, project_root: Path) -> dict:
    """Run Jest on js_test_dir, copying source files alongside tests."""
    node_bin = shutil.which("node")
    npx_bin  = shutil.which("npx")
    if not node_bin:
        msg = "node not found on PATH — install Node.js to run JavaScript tests"
        logger.warning(f"[Stage 4] {msg}")
        return _empty_result(msg)

    # Ensure Jest is available or install inline
    jest_cmd = _resolve_jest_cmd(js_test_dir, project_root)

    logger.info(f"[Stage 4] Running Jest in: {js_test_dir}")

    # Jest needs source files next to tests. Copy .js source files temporarily.
    _copy_source_files_for_lang(project_root, js_test_dir, ".js")

    # Create a minimal Jest config so it doesn't need package.json
    jest_config = js_test_dir / "jest.config.js"
    if not jest_config.exists():
        jest_config.write_text(
            "module.exports = { testEnvironment: 'node', testMatch: ['**/*.test.js'] };\n",
            encoding="utf-8",
        )

    try:
        result = subprocess.run(
            jest_cmd + [
                "--no-coverage",
                "--verbose",
                "--forceExit",          # don't hang on open handles
                "--passWithNoTests",    # exit 0 if no test files found
            ],
            cwd=str(js_test_dir),
            capture_output=True,
            text=True,
            timeout=config.PYTEST_TIMEOUT,
        )
        raw_output = result.stdout + result.stderr
        return _parse_jest_output(raw_output)

    except subprocess.TimeoutExpired:
        msg = f"Jest timed out after {config.PYTEST_TIMEOUT}s"
        logger.error(f"[Stage 4] {msg}")
        return _empty_result(msg)
    except FileNotFoundError as e:
        msg = f"Jest runner not found: {e}"
        logger.error(f"[Stage 4] {msg}")
        return _empty_result(msg)
    except Exception as e:
        logger.error(f"[Stage 4] JS runner error: {e}")
        return _empty_result(str(e))


def _resolve_jest_cmd(js_test_dir: Path, project_root: Path) -> list[str]:
    """Return the command list to invoke Jest."""
    # Check if jest is already installed in project node_modules
    local_jest = project_root / "node_modules" / ".bin" / "jest"
    if local_jest.exists():
        return [str(local_jest)]

    local_jest2 = js_test_dir / "node_modules" / ".bin" / "jest"
    if local_jest2.exists():
        return [str(local_jest2)]

    npx_bin = shutil.which("npx")
    if npx_bin:
        return [npx_bin, "jest"]

    # Fallback to global jest
    jest_bin = shutil.which("jest")
    if jest_bin:
        return [jest_bin]

    # Install jest locally in the js_test_dir
    logger.info("[Stage 4] Jest not found — installing locally via npm...")
    subprocess.run(
        ["npm", "init", "-y"],
        cwd=str(js_test_dir),
        capture_output=True,
    )
    subprocess.run(
        ["npm", "install", "--save-dev", "jest"],
        cwd=str(js_test_dir),
        capture_output=True,
        timeout=120,
    )
    return [str(js_test_dir / "node_modules" / ".bin" / "jest")]


# ─────────────────────────────────────────────────────────────────────────────
#  Go runner (go test)
# ─────────────────────────────────────────────────────────────────────────────

def _run_go_tests(go_test_dir: Path, project_root: Path) -> dict:
    """Run 'go test' for generated Go test files."""
    go_bin = shutil.which("go")
    if not go_bin:
        msg = "go not found on PATH — install Go to run Go tests"
        logger.warning(f"[Stage 4] {msg}")
        return _empty_result(msg)

    # Copy .go source files alongside the test files so they share a package
    _copy_source_files_for_lang(project_root, go_test_dir, ".go")

    # Ensure go.mod exists (needed to run standalone packages)
    go_mod = go_test_dir / "go.mod"
    if not go_mod.exists():
        logger.info("[Stage 4] Creating go.mod for generated Go tests")
        subprocess.run(
            [go_bin, "mod", "init", "generated_tests"],
            cwd=str(go_test_dir),
            capture_output=True,
        )

    logger.info(f"[Stage 4] Running go test in: {go_test_dir}")
    try:
        result = subprocess.run(
            [go_bin, "test", "-v", "./..."],
            cwd=str(go_test_dir),
            capture_output=True,
            text=True,
            timeout=config.PYTEST_TIMEOUT,
        )
        raw_output = result.stdout + result.stderr
        return _parse_go_output(raw_output)

    except subprocess.TimeoutExpired:
        msg = f"go test timed out after {config.PYTEST_TIMEOUT}s"
        logger.error(f"[Stage 4] {msg}")
        return _empty_result(msg)
    except Exception as e:
        logger.error(f"[Stage 4] Go runner error: {e}")
        return _empty_result(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  Java runner (javac + JUnit 5 standalone)
# ─────────────────────────────────────────────────────────────────────────────

def _run_java_tests(java_test_dir: Path, project_root: Path) -> dict:
    """Compile and run JUnit 5 tests using the standalone console launcher."""
    javac_bin = shutil.which("javac")
    java_bin  = shutil.which("java")
    mvn_bin   = shutil.which("mvn") or shutil.which("mvnw")

    if not java_bin:
        msg = "java not found on PATH — install JDK to run Java tests"
        logger.warning(f"[Stage 4] {msg}")
        return _empty_result(msg)

    # Copy .java source files alongside tests
    _copy_source_files_for_lang(project_root, java_test_dir, ".java")

    # Prefer Maven if pom.xml is in project root
    pom_file = project_root / "pom.xml"
    if pom_file.exists() and mvn_bin:
        return _run_java_maven(java_test_dir, project_root, mvn_bin)

    # Fallback: standalone JUnit jar
    return _run_java_standalone(java_test_dir, java_bin, javac_bin)


def _run_java_maven(java_test_dir: Path, project_root: Path, mvn_bin: str) -> dict:
    """Run Maven tests (pom.xml detected)."""
    logger.info(f"[Stage 4] Running Maven tests in: {project_root}")
    try:
        result = subprocess.run(
            [mvn_bin, "test", "-f", str(project_root / "pom.xml")],
            capture_output=True,
            text=True,
            timeout=config.PYTEST_TIMEOUT * 2,
        )
        raw_output = result.stdout + result.stderr
        return _parse_maven_output(raw_output)
    except Exception as e:
        logger.error(f"[Stage 4] Maven runner error: {e}")
        return _empty_result(str(e))


def _run_java_standalone(java_test_dir: Path, java_bin: str, javac_bin: str | None) -> dict:
    """Compile and run JUnit 5 tests using the standalone console launcher JAR."""
    # Ensure the JAR is available
    if not _ensure_junit_jar():
        msg = (
            "JUnit standalone JAR not available. "
            "Download it manually from Maven Central and place it at: "
            f"{JUNIT_JAR_PATH}"
        )
        logger.warning(f"[Stage 4] {msg}")
        return _empty_result(msg)

    if not javac_bin:
        msg = "javac not found — install JDK (not just JRE) to compile Java tests"
        logger.warning(f"[Stage 4] {msg}")
        return _empty_result(msg)

    java_files = list(java_test_dir.glob("*.java"))
    if not java_files:
        return _empty_result("No .java files found in test dir")

    classes_dir = java_test_dir / "classes"
    classes_dir.mkdir(exist_ok=True)

    logger.info(f"[Stage 4] Compiling {len(java_files)} Java file(s)...")

    compile_cmd = [
        javac_bin,
        "-cp", str(JUNIT_JAR_PATH),
        "-d", str(classes_dir),
    ] + [str(f) for f in java_files]

    try:
        compile_result = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        compile_output = compile_result.stdout + compile_result.stderr

        if compile_result.returncode != 0:
            logger.warning(f"[Stage 4] Java compilation errors:\n{compile_output}")
            # Still try to run any classes that compiled
        else:
            logger.info("[Stage 4] Java compilation successful")

        # Run tests
        run_cmd = [
            java_bin,
            "-cp", f"{classes_dir}{os.pathsep}{JUNIT_JAR_PATH}",
            "org.junit.platform.console.ConsoleLauncher",
            "--scan-classpath",
            "--disable-banner",
        ]

        run_result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            timeout=config.PYTEST_TIMEOUT,
        )
        raw_output = compile_output + "\n" + run_result.stdout + run_result.stderr
        return _parse_junit_output(raw_output)

    except subprocess.TimeoutExpired:
        msg = f"Java test run timed out after {config.PYTEST_TIMEOUT}s"
        logger.error(f"[Stage 4] {msg}")
        return _empty_result(msg)
    except Exception as e:
        logger.error(f"[Stage 4] Java standalone runner error: {e}")
        return _empty_result(str(e))


def _ensure_junit_jar() -> bool:
    """Return True if the JUnit standalone JAR is present (download if possible)."""
    if JUNIT_JAR_PATH.exists():
        return True
    JUNIT_JAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"[Stage 4] Downloading JUnit standalone JAR → {JUNIT_JAR_PATH}")
    try:
        import urllib.request
        urllib.request.urlretrieve(JUNIT_STANDALONE_JAR_URL, str(JUNIT_JAR_PATH))
        logger.info("[Stage 4] JUnit JAR downloaded successfully")
        return True
    except Exception as e:
        logger.warning(f"[Stage 4] Could not download JUnit JAR: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Source file copying helper
# ─────────────────────────────────────────────────────────────────────────────

def _copy_source_files_for_lang(project_root: Path, dest_dir: Path, ext: str) -> None:
    """
    Copy source files with the given extension from project_root into dest_dir
    so test runners can resolve imports from the same directory.
    Only copies if the file does not already exist there.
    """
    import shutil as _shutil
    for src_file in project_root.rglob(f"*{ext}"):
        # Skip files already inside the output dir or test dir itself
        try:
            src_file.relative_to(dest_dir)
            continue  # already inside dest
        except ValueError:
            pass
        try:
            src_file.relative_to(project_root / "output")
            continue  # skip output dir
        except ValueError:
            pass

        dest_file = dest_dir / src_file.name
        if not dest_file.exists():
            try:
                _shutil.copy2(str(src_file), str(dest_file))
                logger.debug(f"  Copied {src_file.name} → {dest_dir}")
            except Exception as e:
                logger.debug(f"  Could not copy {src_file.name}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Output parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_pytest_json_report(json_path: Path, raw_output: str) -> dict:
    """Parse the pytest-json-report JSON file into our standard format."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"  Could not parse pytest JSON report: {e}")
        return _parse_stdout_fallback(raw_output, language="python")

    summary_raw = data.get("summary", {})
    tests_raw   = data.get("tests", [])

    tests = []
    for t in tests_raw:
        call     = t.get("call", {})
        longrepr = str(call["longrepr"])[:800] if call.get("longrepr") else ""
        tests.append({
            "node_id":     t.get("nodeid", ""),
            "name":        t.get("nodeid", "").split("::")[-1],
            "outcome":     t.get("outcome", "unknown"),
            "duration":    round(t.get("duration", 0), 3),
            "source_file": _extract_source_from_nodeid(t.get("nodeid", "")),
            "language":    "python",
            "error":       longrepr,
        })

    return {
        "summary": {
            "total":  summary_raw.get("total", len(tests)),
            "passed": summary_raw.get("passed", 0),
            "failed": summary_raw.get("failed", 0),
            "errors": summary_raw.get("error",  0),
        },
        "tests":      tests,
        "raw_output": raw_output,
    }


def _parse_jest_output(raw_output: str) -> dict:
    """
    Parse Jest verbose output into our standard format.

    Jest verbose output lines look like:
      ✓ adds two numbers (3ms)
      ✕ divides by zero
      ✓ returns empty string
    Summary lines:
      Tests: 2 passed, 1 failed, 3 total
    """
    tests   = []
    passed  = 0
    failed  = 0
    errors  = 0
    current_suite = "unknown"

    # Detect suite name lines (e.g. "  PASS  calculator.test.js" or "  FAIL  ...")
    for line in raw_output.splitlines():
        suite_m = re.match(r"\s*(PASS|FAIL)\s+(.+\.test\.js)", line)
        if suite_m:
            current_suite = suite_m.group(2).strip()
            continue

        # Individual test lines: "    ✓ test name (Xms)" or "    ✕ test name"
        pass_m = re.match(r"\s*[✓✔√]\s+(.+?)(?:\s+\(\d+\s*ms\))?$", line)
        if pass_m:
            tests.append({
                "node_id":     f"{current_suite}::{pass_m.group(1).strip()}",
                "name":        pass_m.group(1).strip(),
                "outcome":     "passed",
                "duration":    0,
                "source_file": re.sub(r"\.test\.js$", ".js", current_suite),
                "language":    "javascript",
                "error":       "",
            })
            passed += 1
            continue

        fail_m = re.match(r"\s*[✕✗×]\s+(.+?)(?:\s+\(\d+\s*ms\))?$", line)
        if fail_m:
            tests.append({
                "node_id":     f"{current_suite}::{fail_m.group(1).strip()}",
                "name":        fail_m.group(1).strip(),
                "outcome":     "failed",
                "duration":    0,
                "source_file": re.sub(r"\.test\.js$", ".js", current_suite),
                "language":    "javascript",
                "error":       "",
            })
            failed += 1
            continue

    # Also parse the summary line as a sanity check / fallback
    summary_m = re.search(
        r"Tests:\s*(?:(\d+)\s+failed,\s*)?(?:(\d+)\s+passed,\s*)?(\d+)\s+total",
        raw_output,
    )
    if summary_m and not tests:
        failed  = int(summary_m.group(1) or 0)
        passed  = int(summary_m.group(2) or 0)
        total   = int(summary_m.group(3) or 0)
        errors  = total - passed - failed

    total = passed + failed + errors
    return {
        "summary": {"total": total, "passed": passed, "failed": failed, "errors": errors},
        "tests":   tests,
        "raw_output": raw_output,
    }


def _parse_go_output(raw_output: str) -> dict:
    """
    Parse 'go test -v' output.

    Lines look like:
      --- PASS: TestAdd (0.00s)
      --- FAIL: TestDiv (0.00s)
      ok  	generated_tests	0.123s
      FAIL	generated_tests	0.456s
    """
    tests  = []
    passed = 0
    failed = 0
    errors = 0

    for line in raw_output.splitlines():
        pass_m = re.match(r"--- PASS: (\S+)\s+\((.+?)s\)", line)
        if pass_m:
            tests.append({
                "node_id":     pass_m.group(1),
                "name":        pass_m.group(1),
                "outcome":     "passed",
                "duration":    float(pass_m.group(2)),
                "source_file": "",
                "language":    "go",
                "error":       "",
            })
            passed += 1
            continue

        fail_m = re.match(r"--- FAIL: (\S+)\s+\((.+?)s\)", line)
        if fail_m:
            tests.append({
                "node_id":     fail_m.group(1),
                "name":        fail_m.group(1),
                "outcome":     "failed",
                "duration":    float(fail_m.group(2)),
                "source_file": "",
                "language":    "go",
                "error":       "",
            })
            failed += 1

    total = passed + failed + errors
    return {
        "summary": {"total": total, "passed": passed, "failed": failed, "errors": errors},
        "tests":   tests,
        "raw_output": raw_output,
    }


def _parse_junit_output(raw_output: str) -> dict:
    """
    Parse JUnit Platform Console Launcher output.

    Relevant lines:
      [         1 tests successful      ]
      [         2 tests failed          ]
      MethodSource [...] - TestMethod
    """
    tests  = []
    passed = 0
    failed = 0
    errors = 0

    # Extract counts from summary
    ok_m  = re.search(r"\[\s*(\d+)\s+tests? successful\s*\]", raw_output)
    nok_m = re.search(r"\[\s*(\d+)\s+tests? failed\s*\]", raw_output)
    if ok_m:
        passed = int(ok_m.group(1))
    if nok_m:
        failed = int(nok_m.group(1))

    # Extract individual test names from the tree output
    # e.g.  "  +-- [OK] testAdd()"  or  "  +-- [X] testDivideByZero()"
    for line in raw_output.splitlines():
        ok_test = re.search(r"\[OK\]\s+(\w[\w<>]*\(\))", line)
        if ok_test:
            tests.append({
                "node_id":     ok_test.group(1),
                "name":        ok_test.group(1),
                "outcome":     "passed",
                "duration":    0,
                "source_file": "",
                "language":    "java",
                "error":       "",
            })
            continue
        fail_test = re.search(r"\[X\]\s+(\w[\w<>]*\(\))", line)
        if fail_test:
            tests.append({
                "node_id":     fail_test.group(1),
                "name":        fail_test.group(1),
                "outcome":     "failed",
                "duration":    0,
                "source_file": "",
                "language":    "java",
                "error":       "",
            })

    # If no individual tests found but counts exist, synthesise placeholders
    if not tests and (passed + failed) > 0:
        for i in range(passed):
            tests.append({"node_id": f"java_test_{i}", "name": f"java_test_{i}",
                           "outcome": "passed", "duration": 0,
                           "source_file": "", "language": "java", "error": ""})
        for i in range(failed):
            tests.append({"node_id": f"java_fail_{i}", "name": f"java_fail_{i}",
                           "outcome": "failed", "duration": 0,
                           "source_file": "", "language": "java", "error": ""})

    total = passed + failed + errors
    return {
        "summary": {"total": total, "passed": passed, "failed": failed, "errors": errors},
        "tests":   tests,
        "raw_output": raw_output,
    }


def _parse_maven_output(raw_output: str) -> dict:
    """Parse 'mvn test' output (Surefire format)."""
    tests  = []
    passed = 0
    failed = 0
    errors = 0

    # Surefire summary: "Tests run: 3, Failures: 1, Errors: 0, Skipped: 0"
    for line in raw_output.splitlines():
        m = re.search(
            r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)",
            line,
        )
        if m:
            total_run = int(m.group(1))
            failures  = int(m.group(2))
            errs      = int(m.group(3))
            passed   += total_run - failures - errs
            failed   += failures
            errors   += errs

    total = passed + failed + errors
    return {
        "summary": {"total": total, "passed": passed, "failed": failed, "errors": errors},
        "tests":   tests,
        "raw_output": raw_output,
    }


def _parse_stdout_fallback(raw_output: str, language: str = "python") -> dict:
    """Generic fallback parser — extracts pass/fail counts from last summary line."""
    passed = failed = errors = 0

    lines = raw_output.splitlines()
    for line in reversed(lines):
        pm = re.findall(r"(\d+) (passed|failed|error)", line)
        for count, kind in pm:
            if kind == "passed":  passed = int(count)
            elif kind == "failed": failed = int(count)
            elif kind == "error":  errors = int(count)
        if pm:
            break

    return {
        "summary": {
            "total":  passed + failed + errors,
            "passed": passed,
            "failed": failed,
            "errors": errors,
        },
        "tests":      [],
        "raw_output": raw_output,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Misc helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_source_from_nodeid(node_id: str) -> str:
    """
    Map a pytest node ID back to its likely source file.
    e.g. "output/generated_tests/test_calculator_py.py::TestCalc::test_add"
         → "calculator.py"
    """
    parts    = node_id.replace("\\", "/").split("/")
    filename = parts[-1].split("::")[0]

    if filename.startswith("test_") and filename.endswith(".py"):
        stem = filename[5:-3]
        stem = re.sub(r"_py$", ".py", stem)
        stem = re.sub(r"_js$", ".js", stem)
        stem = re.sub(r"_ts$", ".ts", stem)
        return stem
    return filename


def _empty_result(reason: str) -> dict:
    return {
        "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0},
        "tests":   [],
        "raw_output": reason,
        "error":   reason,
    }
