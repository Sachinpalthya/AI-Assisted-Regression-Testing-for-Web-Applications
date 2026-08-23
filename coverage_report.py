#!/usr/bin/env python3
"""
coverage_report.py — Standalone Code Coverage Report Generator

Measures code coverage for sample files tested across Python, JavaScript, Go, and Java.
Generates terminal summary table, JSON report, and an interactive HTML report.

Usage:
    python coverage_report.py <path/to/project>

Example:
    python coverage_report.py ./sample_project
"""

import argparse
import sys
import time
from pathlib import Path

# pyrefly: ignore [missing-import]
from rich.console import Console
# pyrefly: ignore [missing-import]
from rich.panel import Panel
# pyrefly: ignore [missing-import]
from rich.table import Table
# pyrefly: ignore [missing-import]
from rich.text import Text
# pyrefly: ignore [missing-import]
from rich.rule import Rule

import config
from utils.file_utils import save_json, ensure_output_dirs
from utils.coverage_utils import run_coverage_analysis, build_coverage_html_report

console = Console()


def print_banner() -> None:
    console.print()
    console.print(Panel.fit(
        Text.from_markup(
            "[bold cyan]📊 Multi-Language Code Coverage Generator[/bold cyan]\n"
            "[dim]Standalone report for all sample files used in regression testing[/dim]"
        ),
        border_style="bright_cyan",
        padding=(1, 4),
    ))
    console.print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python coverage_report.py",
        description="Standalone Multi-Language Code Coverage Report Generator",
    )
    parser.add_argument(
        "project_path",
        type=Path,
        nargs="?",
        default=Path("./sample_project"),
        help="Path to analyzed project directory (default: ./sample_project)",
    )

    args = parser.parse_args()
    project_path = args.project_path.resolve()

    if not project_path.exists():
        console.print(f"[bold red]Error:[/bold red] Project directory does not exist: {project_path}")
        sys.exit(1)

    config.set_project_path(project_path)
    ensure_output_dirs()

    print_banner()
    console.print(f"  [cyan]Project Path  :[/cyan] {project_path}")
    console.print(f"  [cyan]Generated Tests:[/cyan] {config.GENERATED_TESTS_DIR.resolve()}")
    console.print()

    start_time = time.time()
    console.print(Rule("[bold cyan]Calculating Code Coverage[/bold cyan]", style="cyan"))

    # Compute coverage across all languages
    report_data = run_coverage_analysis(project_path)

    # 1. Terminal Table Output using rich
    table = Table(title="Sample Files Code Coverage", border_style="cyan", header_style="bold magenta")
    table.add_column("Sample File", style="cyan")
    table.add_column("Language", style="yellow")
    table.add_column("Coverage %", justify="right", style="bold green")
    table.add_column("Covered Lines", justify="right", style="green")
    table.add_column("Missed Lines", justify="right", style="red")
    table.add_column("Total Lines", justify="right", style="dim")

    for f in report_data["files"]:
        cov_val = f["coverage_percent"]
        color = "green" if cov_val >= 80 else ("yellow" if cov_val >= 50 else "red")
        table.add_row(
            f["file"],
            f["language"].upper(),
            f"[{color}]{cov_val:.1f}%[/{color}]",
            str(len(f["covered_lines"])),
            str(len(f["missing_lines"])),
            str(f["total_lines"]),
        )

    console.print()
    console.print(table)
    console.print()

    # 2. Output Paths
    json_path = config.OUTPUT_DIR / "coverage_report.json"
    html_path = config.OUTPUT_DIR / "coverage_report.html"

    # Save reports
    save_json(report_data, json_path)
    build_coverage_html_report(report_data, html_path)

    elapsed = round(time.time() - start_time, 2)
    console.print(Panel.fit(
        Text.from_markup(
            f"[bold green]Coverage Analysis Complete![/bold green] ({elapsed}s)\n\n"
            f"[cyan]Overall Coverage :[/cyan] [bold green]{report_data['overall_coverage']}%[/bold green]\n"
            f"[cyan]HTML Report      :[/cyan] [underline]{html_path.resolve()}[/underline]\n"
            f"[cyan]JSON Data        :[/cyan] [underline]{json_path.resolve()}[/underline]"
        ),
        border_style="green",
        padding=(1, 4),
    ))
    console.print()


if __name__ == "__main__":
    main()
