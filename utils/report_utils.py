"""
utils/report_utils.py — Builds the final HTML dashboard report.

Uses Jinja2 templating with inline HTML/CSS/JS to produce a self-contained
single-file report at output/report.html.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Inline Jinja2 HTML Template ────────────────────────────────────────────
REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>AI Regression Test Report</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d2e; --card: #212438;
    --border: #2e3250; --accent: #7c6af7; --accent2: #56cfb2;
    --pass: #4ade80; --fail: #f87171; --warn: #fbbf24;
    --text: #e2e8f0; --muted: #8892b0; --code-bg: #0d1117;
    --font: 'Segoe UI', system-ui, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--font); }

  /* ── Header ── */
  .header {
    background: linear-gradient(135deg, #1a1d2e 0%, #212438 100%);
    border-bottom: 1px solid var(--border);
    padding: 2rem 2.5rem;
    display: flex; align-items: center; gap: 1.5rem;
  }
  .header-icon { font-size: 2.5rem; }
  .header h1 { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px; }
  .header h1 span { color: var(--accent); }
  .header-meta { margin-left: auto; text-align: right; color: var(--muted); font-size: 0.8rem; }
  .header-meta strong { display: block; color: var(--text); font-size: 1rem; }

  /* ── Layout ── */
  .container { max-width: 1300px; margin: 0 auto; padding: 2rem 2.5rem; }

  /* ── Stats Bar ── */
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem; margin-bottom: 2rem;
  }
  .stat-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.25rem 1.5rem;
    display: flex; flex-direction: column; gap: 0.4rem;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .stat-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
  .stat-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
  .stat-value { font-size: 2rem; font-weight: 800; }
  .stat-value.pass  { color: var(--pass); }
  .stat-value.fail  { color: var(--fail); }
  .stat-value.warn  { color: var(--warn); }
  .stat-value.total { color: var(--accent); }
  .stat-value.files { color: var(--accent2); }

  /* ── Progress Bar ── */
  .progress-section { margin-bottom: 2rem; }
  .progress-label { display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.85rem; color: var(--muted); }
  .progress-bar { height: 10px; background: var(--surface); border-radius: 9999px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 9999px; transition: width 1s ease;
    background: linear-gradient(90deg, var(--pass), var(--accent2)); }

  /* ── Section Titles ── */
  .section-title {
    font-size: 1.1rem; font-weight: 700; color: var(--text);
    margin: 2.5rem 0 1rem; display: flex; align-items: center; gap: 0.6rem;
  }
  .section-title::after {
    content: ''; flex: 1; height: 1px; background: var(--border);
  }

  /* ── File Cards ── */
  .file-grid { display: flex; flex-direction: column; gap: 1rem; }
  .file-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; overflow: hidden;
  }
  .file-card-header {
    padding: 1rem 1.25rem; display: flex; align-items: center; gap: 0.75rem;
    cursor: pointer; user-select: none;
    border-bottom: 1px solid transparent;
    transition: background 0.15s;
  }
  .file-card-header:hover { background: rgba(124,106,247,0.07); }
  .file-card-header.expanded { border-bottom-color: var(--border); }
  .file-badge {
    padding: 0.2rem 0.65rem; border-radius: 9999px; font-size: 0.7rem;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .badge-pass  { background: rgba(74,222,128,0.15); color: var(--pass); }
  .badge-fail  { background: rgba(248,113,113,0.15); color: var(--fail); }
  .badge-error { background: rgba(251,191,36,0.15);  color: var(--warn); }
  .file-path { font-size: 0.9rem; font-family: monospace; color: var(--accent2); flex: 1; }
  .file-counts { font-size: 0.8rem; color: var(--muted); margin-left: auto; white-space: nowrap; }
  .chevron { transition: transform 0.2s; color: var(--muted); }
  .chevron.open { transform: rotate(180deg); }
  .file-card-body { padding: 1.25rem; display: none; }
  .file-card-body.visible { display: block; }

  /* ── Test Items ── */
  .test-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .test-item {
    display: flex; align-items: flex-start; gap: 0.75rem;
    padding: 0.75rem 1rem; border-radius: 8px;
    background: var(--surface); border: 1px solid var(--border);
  }
  .test-icon { font-size: 1rem; margin-top: 1px; flex-shrink: 0; }
  .test-name { font-size: 0.85rem; font-family: monospace; color: var(--text); flex: 1; }
  .test-detail { font-size: 0.78rem; color: var(--muted); margin-top: 0.25rem; }
  .test-error {
    margin-top: 0.5rem; padding: 0.6rem 0.8rem;
    background: var(--code-bg); border-left: 3px solid var(--fail);
    border-radius: 4px; font-family: monospace; font-size: 0.75rem;
    color: #fca5a5; white-space: pre-wrap; word-break: break-all;
    max-height: 150px; overflow-y: auto;
  }

  /* ── Analysis & Suggestions ── */
  .analysis-grid { display: flex; flex-direction: column; gap: 1rem; }
  .analysis-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.25rem 1.5rem;
  }
  .analysis-card h3 { font-size: 0.9rem; color: var(--accent); margin-bottom: 0.5rem; font-family: monospace; }
  .analysis-card .root-cause { color: var(--text); font-size: 0.88rem; margin-bottom: 0.75rem; }
  .severity-badge {
    display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
  }
  .sev-high   { background: rgba(248,113,113,0.2); color: var(--fail); }
  .sev-medium { background: rgba(251,191,36,0.2);  color: var(--warn); }
  .sev-low    { background: rgba(74,222,128,0.2);  color: var(--pass); }

  /* ── Code Suggestions ── */
  .suggestion-block { margin-top: 0.75rem; }
  .suggestion-block h4 { font-size: 0.78rem; color: var(--muted); margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: 0.5px; }
  pre.diff {
    background: var(--code-bg); border-radius: 6px; padding: 0.75rem;
    font-size: 0.75rem; overflow-x: auto; white-space: pre; border: 1px solid var(--border);
  }
  pre.diff .add  { color: var(--pass); }
  pre.diff .rem  { color: var(--fail); }
  pre.diff .ctx  { color: var(--muted); }

  /* ── Empty State ── */
  .empty-state { text-align: center; padding: 3rem; color: var(--muted); }
  .empty-state .icon { font-size: 3rem; margin-bottom: 1rem; }

  /* ── Footer ── */
  footer {
    border-top: 1px solid var(--border); padding: 1.5rem 2.5rem;
    text-align: center; color: var(--muted); font-size: 0.78rem;
    margin-top: 3rem;
  }
  footer a { color: var(--accent); text-decoration: none; }
</style>
</head>
<body>

<!-- ── Header ── -->
<div class="header">
  <span class="header-icon">🧪</span>
  <div>
    <h1>AI <span>Regression</span> Test Report</h1>
    <div style="color:var(--muted);font-size:0.82rem;">Powered by Ollama · {{ model }}</div>
  </div>
  <div class="header-meta">
    <strong>{{ project_root }}</strong>
    Generated {{ generated_at }}
  </div>
</div>

<!-- ── Main ── -->
<div class="container">

  <!-- Stats -->
  <div class="stats-grid">
    <div class="stat-card">
      <span class="stat-label">Total Tests</span>
      <span class="stat-value total">{{ stats.total }}</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Passed</span>
      <span class="stat-value pass">{{ stats.passed }}</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Failed</span>
      <span class="stat-value fail">{{ stats.failed }}</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Errors</span>
      <span class="stat-value warn">{{ stats.errors }}</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Files Tested</span>
      <span class="stat-value files">{{ stats.files_tested }}</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Pass Rate</span>
      <span class="stat-value" style="color:var(--accent2)">{{ stats.pass_rate }}%</span>
    </div>
  </div>

  <!-- Progress Bar -->
  <div class="progress-section">
    <div class="progress-label">
      <span>Test Pass Rate</span>
      <span>{{ stats.passed }} / {{ stats.total }} tests passing</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" style="width:{{ stats.pass_rate }}%"></div>
    </div>
  </div>

  <!-- Per-file Results -->
  <div class="section-title">📁 Test Results by File</div>
  <div class="file-grid">
    {% if file_results %}
      {% for file in file_results %}
      <div class="file-card">
        <div class="file-card-header" onclick="toggleCard(this)">
          <span class="file-badge badge-{{ file.status }}">{{ file.status }}</span>
          <span class="file-path">{{ file.source_file }}</span>
          <span class="file-counts">{{ file.passed }}✅ {{ file.failed }}❌ {{ file.errors }}⚠️</span>
          <span class="chevron">▼</span>
        </div>
        <div class="file-card-body">
          <div class="test-list">
            {% for test in file.tests %}
            <div class="test-item">
              <span class="test-icon">{% if test.outcome == 'passed' %}✅{% elif test.outcome == 'failed' %}❌{% else %}⚠️{% endif %}</span>
              <div style="flex:1">
                <div class="test-name">{{ test.name }}</div>
                {% if test.duration %}
                <div class="test-detail">Duration: {{ test.duration }}s</div>
                {% endif %}
                {% if test.error %}
                <div class="test-error">{{ test.error }}</div>
                {% endif %}
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
      {% endfor %}
    {% else %}
      <div class="empty-state">
        <div class="icon">📭</div>
        No test results available yet.
      </div>
    {% endif %}
  </div>

  <!-- Failure Analysis -->
  <div class="section-title">🔍 AI Failure Analysis</div>
  <div class="analysis-grid">
    {% if failures %}
      {% for f in failures %}
      <div class="analysis-card">
        <h3>{{ f.test_name }}</h3>
        <div style="margin-bottom:0.5rem">
          <span class="severity-badge sev-{{ f.severity }}">{{ f.severity }} severity</span>
          &nbsp;
          <span style="font-size:0.8rem;color:var(--muted)">Source: <code style="color:var(--accent2)">{{ f.source_file }}</code></span>
        </div>
        <div class="root-cause">{{ f.root_cause }}</div>
        {% if f.suggestion %}
        <div class="suggestion-block">
          <h4>💡 Suggested Fix</h4>
          <pre class="diff">{{ f.suggestion }}</pre>
        </div>
        {% endif %}
      </div>
      {% endfor %}
    {% else %}
      <div class="empty-state">
        <div class="icon">🎉</div>
        No failures to analyze — all tests passed!
      </div>
    {% endif %}
  </div>

  <!-- Code Suggestions Summary -->
  {% if suggestions %}
  <div class="section-title">🛠️ Code Improvement Suggestions</div>
  <div class="analysis-grid">
    {% for s in suggestions %}
    <div class="analysis-card">
      <h3>{{ s.source_file }}</h3>
      <div class="root-cause" style="white-space:pre-wrap">{{ s.suggestion_text }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

</div>

<footer>
  Generated by <strong>AI Regression Testing Framework</strong> ·
  Model: <a href="#">{{ model }}</a> ·
  {{ generated_at }}
</footer>

<script>
function toggleCard(header) {
  const body = header.nextElementSibling;
  const chevron = header.querySelector('.chevron');
  const isOpen = body.classList.contains('visible');
  body.classList.toggle('visible', !isOpen);
  chevron.classList.toggle('open', !isOpen);
  header.classList.toggle('expanded', !isOpen);
}
// Auto-expand first failing card
document.addEventListener('DOMContentLoaded', () => {
  const first = document.querySelector('.badge-fail');
  if (first) first.closest('.file-card-header').click();
});
</script>
</body>
</html>
"""


def build_html_report(
    project_root: str,
    model: str,
    stats: dict,
    file_results: list,
    failures: list,
    suggestions: list,
    output_path: Path,
) -> None:
    """Render the Jinja2 template and write to output_path."""
    try:
        from jinja2 import Environment
        env = Environment(autoescape=True)
        template = env.from_string(REPORT_TEMPLATE)
        html = template.render(
            project_root=project_root,
            model=model,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            stats=stats,
            file_results=file_results,
            failures=failures,
            suggestions=suggestions,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML report written → {output_path}")
    except Exception as e:
        logger.error(f"Failed to build HTML report: {e}")
        raise
