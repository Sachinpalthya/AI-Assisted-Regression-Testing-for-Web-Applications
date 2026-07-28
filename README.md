# AI-Assisted Regression Testing Framework

> **MSc Computing — University of Roehampton**  
> Author: Sachin Palthya  
> Powered by: [Ollama](https://ollama.com) (local LLM)

An intelligent regression testing pipeline that automatically:
1. Scans your project codebase and builds context
2. Identifies which files need tests
3. Generates pytest tests file by file using a local LLM
4. Runs the tests and captures results
5. Analyses failures and identifies root causes
6. Suggests concrete code fixes

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Ollama & Pull a Model
```bash
# Start the Ollama server (if not already running)
ollama serve

# Pull a code-capable model (choose one)
ollama pull codellama        # recommended — code-specialized
ollama pull llama3           # good general purpose
ollama pull deepseek-coder   # strong code model
ollama pull mistral          # fast and capable
```

### 3. Run the Framework
```bash
# Test on the included sample project
python main.py ./sample_project

# Test on any real project
python main.py /path/to/your/project

# Use a different model
python main.py ./sample_project --model llama3

# Verbose output
python main.py ./sample_project --log-level DEBUG
```

### 4. View the Report
Open `output/report.html` in your browser for the full interactive dashboard.

---

## 📁 Project Structure

```
sachin/
├── main.py                        # CLI entry point
├── config.py                      # Configuration (model, paths, extensions)
├── requirements.txt
│
├── pipeline/
│   ├── context_builder.py         # Stage 1 — Scan & build codebase context
│   ├── file_selector.py           # Stage 2 — LLM picks testable files
│   ├── test_generator.py          # Stage 3 — LLM generates pytest tests
│   ├── test_runner.py             # Stage 4 — Run tests with pytest
│   ├── report_analyzer.py         # Stage 5 — LLM analyzes failures
│   └── code_suggester.py          # Stage 6 — LLM suggests code fixes
│
├── utils/
│   ├── ollama_client.py           # Ollama SDK wrapper
│   ├── file_utils.py              # File reading, path utilities
│   └── report_utils.py           # HTML dashboard generator
│
├── sample_project/                # Demo project for testing
│   ├── calculator.py
│   ├── string_utils.py
│   └── user_manager.py
│
└── output/                        # Auto-created at runtime
    ├── context.json               # Stage 1 output
    ├── testable_files.json        # Stage 2 output
    ├── generated_tests/           # Stage 3 output (pytest files)
    ├── pytest_raw.txt             # Stage 4 raw output
    ├── pytest_report.json         # Stage 4 structured results
    ├── analysis_report.json       # Stage 5 + 6 analysis
    └── report.html                # Final HTML dashboard
```

---

## ⚙️ Configuration

Edit `config.py` to customise the framework:

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `codellama` | LLM model to use |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address |
| `MAX_LINES_PER_FILE` | `400` | Max lines sent to LLM per file |
| `SUPPORTED_EXTENSIONS` | `.py .js .ts ...` | File types to scan |
| `EXCLUDED_DIRS` | `node_modules, .git ...` | Directories to skip |
| `PYTEST_TIMEOUT` | `120` | Max seconds for pytest run |

---

## 🔄 Pipeline Stages

| # | Stage | Description |
|---|---|---|
| 1 | **Context Builder** | Walks the project folder, reads source files, LLM generates project summary |
| 2 | **File Selector** | LLM decides which files have testable business logic |
| 3 | **Test Generator** | LLM writes pytest tests per file (happy paths, edge cases, exceptions) |
| 4 | **Test Runner** | `pytest` subprocess runs all generated tests, captures JSON + raw output |
| 5 | **Report Analyzer** | LLM explains failures, maps them to source files, assigns severity |
| 6 | **Code Suggester** | LLM provides before/after code fix diffs for each failing source file |

---

## 📊 Output Files

After running, inspect:

- **`output/report.html`** — Interactive dark-mode dashboard with charts, per-file results, failure analysis, and code suggestions
- **`output/analysis_report.json`** — Machine-readable full analysis (suitable for CI integration)
- **`output/generated_tests/`** — The AI-generated test files (useful to review LLM quality)
- **`output/pytest_raw.txt`** — Raw pytest terminal output

---

## 🔧 CLI Options

```
python main.py <project_path> [options]

Arguments:
  project_path         Path to the project folder to analyze

Options:
  --model MODEL        Ollama model name (default: codellama)
  --log-level LEVEL    Logging verbosity: DEBUG|INFO|WARNING|ERROR
  -h, --help           Show help
```

---

## 🧪 Tested With

- [TinyDB](https://github.com/msiemens/tinydb) — Python document store
- Sample project included in this repo

---

## 📋 Requirements

- Python 3.10+
- Ollama running locally (`ollama serve`)
- A code-capable model pulled (`ollama pull codellama`)
- ~4GB RAM for 7B models, ~8GB for 13B models

---

## 📄 License

MIT — open source, academic use encouraged.
