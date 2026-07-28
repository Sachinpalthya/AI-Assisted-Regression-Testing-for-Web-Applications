#!/usr/bin/env python3
"""
main.py — AI-Assisted Regression Testing Framework
University of Roehampton — MSc Computing (Sachin Palthya)

Usage:
    python main.py <path/to/your/project>

Example:
    python main.py ./sample_project
    python main.py /path/to/tinydb
    python main.py /path/to/jsmini
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# pyrefly: ignore [missing-import]
from rich.console import Console
# pyrefly: ignore [missing-import]
from rich.panel import Panel
# pyrefly: ignore [missing-import]
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
# pyrefly: ignore [missing-import]
from rich.rule import Rule
# pyrefly: ignore [missing-import]
from rich.text import Text
# pyrefly: ignore [missing-import]
from rich import print as rprint

import config
from utils.ollama_client import is_available
from utils.file_utils import ensure_output_dirs
from utils.report_utils import build_html_report

from pipeline.context_builder  import build_context
from pipeline.file_selector    import select_testable_files
from pipeline.test_generator   import generate_tests
from pipeline.test_runner      import run_tests
from pipeline.report_analyzer  import analyze_results
from pipeline.code_suggester   import suggest_code_fixes

# ─── Setup ──────────────────────────────────────────────────────────────────
console = Console()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ─── Banner ─────────────────────────────────────────────────────────────────
def print_banner() -> None:
    console.print()
    console.print(Panel.fit(
        Text.from_markup(
            "[bold magenta]🧪 AI-Assisted Regression Testing Framework[/bold magenta]\n"
            "[dim]University of Roehampton · MSc Computing · Sachin Palthya[/dim]\n"
            f"[cyan]Model:[/cyan] [green]{config.OLLAMA_MODEL}[/green]  "
            f"[cyan]Host:[/cyan] [green]{config.OLLAMA_HOST}[/green]"
        ),
        border_style="bright_magenta",
        padding=(1, 4),
    ))
    console.print()


def print_stage(n: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]Stage {n}[/bold cyan] — {title}", style="cyan"))


def print_success(msg: str) -> None:
    console.print(f"  [bold green]✓[/bold green] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"  [bold yellow]⚠[/bold yellow]  {msg}")


def print_error(msg: str) -> None:
    console.print(f"  [bold red]✗[/bold red] {msg}")


# ─── Main Pipeline ──────────────────────────────────────────────────────────
def run_pipeline(project_path: Path) -> int:
    """
    Execute all 6 pipeline stages and return exit code (0=success).
    """
    start_time = time.time()
    print_banner()

    # ── Pre-flight checks ────────────────────────────────────────────────────
    console.print("[bold]Pre-flight checks[/bold]")
    if not project_path.exists():
        print_error(f"Project path does not exist: {project_path}")
        return 1

    console.print(f"  Project root : [green]{project_path.resolve()}[/green]")
    config.set_project_path(project_path.resolve())
    ensure_output_dirs()
    console.print(f"  Output dir   : [green]{config.OUTPUT_DIR.resolve()}[/green]")

    console.print(f"  Checking Ollama at {config.OLLAMA_HOST} ... ", end="")
    if not is_available():
        console.print("[red]FAILED[/red]")
        print_error(
            f"Ollama is not running or model '{config.OLLAMA_MODEL}' is not available.\n"
            f"  1. Start Ollama: ollama serve\n"
            f"  2. Pull model:   ollama pull {config.OLLAMA_MODEL}"
        )
        return 1
    console.print("[green]OK[/green]")

    # ── Stage 1: Context Builder ─────────────────────────────────────────────
    print_stage(1, "Codebase Context Builder")
    context = build_context(project_path)
    print_success(
        f"Indexed {context['total_files']} source file(s) · "
        f"Saved to {config.CONTEXT_FILE}"
    )

    if context["total_files"] == 0:
        print_warning("No source files found. Check SUPPORTED_EXTENSIONS in config.py")
        return 1

    console.print(f"\n[dim italic]{context['summary'][:300]}...[/dim italic]")

    # ── Stage 2: File Selector ───────────────────────────────────────────────
    print_stage(2, "Testable File Selector")
    selected_files = select_testable_files(context)
    print_success(f"Selected {len(selected_files)} file(s) for test generation")
    for f in selected_files:
        console.print(f"    [cyan]→[/cyan] {f['relative_path']}")

    if not selected_files:
        print_warning("No testable files identified. Exiting.")
        return 1

    # ── Stage 3: Test Generator ──────────────────────────────────────────────
    print_stage(3, "Test Generator")
    gen_results = generate_tests(
        selected_files,
        project_summary=context.get("summary", ""),
        project_root=project_path,
    )

    ok_count   = sum(1 for r in gen_results if r["status"] == "ok")
    skip_count  = sum(1 for r in gen_results if r["status"] == "skipped")
    fail_count  = sum(1 for r in gen_results if r["status"] == "failed")

    print_success(f"Generated {ok_count} test file(s)")
    if skip_count:
        print_warning(f"Skipped {skip_count} file(s) (unsupported language)")
    if fail_count:
        print_warning(f"Failed to generate {fail_count} file(s) — check logs")

    # Show which languages had tests generated
    langs_generated = set(r.get("language", "python") for r in gen_results if r["status"] == "ok")
    if langs_generated:
        console.print(f"    [dim]Languages covered: {', '.join(sorted(langs_generated))}[/dim]")

    # ── Stage 4: Test Runner ────────────────────────────────────────────────────
    print_stage(4, "Test Runner (pytest + Jest + go test + JUnit 5)")
    test_results = run_tests(project_path)
    summary = test_results["summary"]

    console.print(
        f"\n  Results: "
        f"[green]{summary['passed']} passed[/green] · "
        f"[red]{summary['failed']} failed[/red] · "
        f"[yellow]{summary['errors']} errors[/yellow] · "
        f"[cyan]{summary['total']} total[/cyan]"
    )

    if summary["total"] == 0:
        print_warning("No tests were executed — check generated_tests/ directory")

    # ── Stage 5: Report Analyzer ─────────────────────────────────────────────
    print_stage(5, "Failure Analyzer")
    analysis = analyze_results(test_results, context)

    if analysis["failures"]:
        console.print(f"\n  Identified [red]{len(analysis['failures'])}[/red] root cause(s):")
        for f in analysis["failures"]:
            sev_color = {"high": "red", "medium": "yellow", "low": "green"}.get(f.get("severity", "medium"), "white")
            console.print(
                f"    [{sev_color}]●[/{sev_color}] {f['test_name']} → {f['root_cause'][:80]}"
            )
    else:
        print_success("No failures — all tests passed!")

    # ── Stage 6: Code Suggester ──────────────────────────────────────────────
    print_stage(6, "Code Improvement Suggester")
    suggestions = suggest_code_fixes(analysis, context)
    if suggestions:
        print_success(f"Suggestions generated for {len(suggestions)} file(s)")
    else:
        print_success("No code changes needed")

    # ── Final Report ─────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold green]Generating Report[/bold green]", style="green"))

    # Build per-file results structure for HTML
    file_results = _build_file_results(test_results)

    build_html_report(
        project_root=str(project_path.resolve()),
        model=config.OLLAMA_MODEL,
        stats={
            "total":       summary["total"],
            "passed":      summary["passed"],
            "failed":      summary["failed"],
            "errors":      summary["errors"],
            "files_tested": len([r for r in gen_results if r["status"] == "ok"]),
            "pass_rate":   analysis.get("pass_rate", 0),
        },
        file_results=file_results,
        failures=analysis.get("failures", []),
        suggestions=suggestions,
        output_path=config.HTML_REPORT_FILE,
    )

    elapsed = round(time.time() - start_time, 1)
    console.print()
    console.print(Panel.fit(
        Text.from_markup(
            f"[bold green]Pipeline Complete![/bold green]  ({elapsed}s)\n\n"
            f"[cyan]HTML Report  :[/cyan] [underline]{config.HTML_REPORT_FILE.resolve()}[/underline]\n"
            f"[cyan]JSON Analysis:[/cyan] [underline]{config.ANALYSIS_REPORT_FILE.resolve()}[/underline]\n"
            f"[cyan]Generated Tests:[/cyan] [underline]{config.GENERATED_TESTS_DIR.resolve()}[/underline]\n\n"
            f"[dim]Open report.html in your browser to view the full dashboard.[/dim]"
        ),
        border_style="green",
        padding=(1, 4),
    ))
    console.print()

    return 0 if summary["failed"] == 0 and summary["errors"] == 0 else 1


def _build_file_results(test_results: dict) -> list[dict]:
    """
    Group test results by source file for the HTML report.
    """
    from collections import defaultdict
    by_file: dict[str, list] = defaultdict(list)

    for test in test_results.get("tests", []):
        src = test.get("source_file", "unknown")
        by_file[src].append(test)

    file_results = []
    for source_file, tests in by_file.items():
        passed = sum(1 for t in tests if t["outcome"] == "passed")
        failed = sum(1 for t in tests if t["outcome"] == "failed")
        errors = sum(1 for t in tests if t["outcome"] == "error")

        if failed > 0 or errors > 0:
            status = "fail"
        elif passed > 0:
            status = "pass"
        else:
            status = "error"

        file_results.append({
            "source_file": source_file,
            "status":      status,
            "passed":      passed,
            "failed":      failed,
            "errors":      errors,
            "tests":       [
                {
                    "name":     t["name"],
                    "outcome":  t["outcome"],
                    "duration": t.get("duration"),
                    "error":    t.get("error", ""),
                }
                for t in tests
            ],
        })

    return file_results


# ─── CLI Entry Point ─────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="AI-Assisted Regression Testing Framework (Ollama-powered)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py ./sample_project
  python main.py /path/to/tinydb
  python main.py . --model llama3
  python main.py ./myapp --model deepseek-coder --log-level DEBUG
        """,
    )
    parser.add_argument(
        "project_path",
        type=Path,
        help="Path to the project folder to analyze and test",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Ollama model to use (default: {config.OLLAMA_MODEL})",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=config.LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )

    args = parser.parse_args()

    # Apply CLI overrides
    if args.model:
        config.OLLAMA_MODEL = args.model
    if args.log_level:
        logging.getLogger().setLevel(getattr(logging, args.log_level))

    exit_code = run_pipeline(args.project_path.resolve())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
