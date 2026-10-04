"""
reporter.py — Data quality report generator.

Produces:
1. An Excel workbook (data_quality_report.xlsx) with:
   - Sheet "Summary"          : dataset-level before/after comparison
   - Sheet "Column Profile - Before" : per-column quality stats (raw)
   - Sheet "Column Profile - After"  : per-column quality stats (clean)
   - Sheet "Validation Results"      : post-cleaning validation checks
   - Sheet "Cleaning Log"            : step-by-step cleaning actions

2. An HTML report (quality_report.html) viewable in any browser.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
import logging
from datetime import datetime

from src.config import (
    REPORTS_DIR,
    REPORTS_HTML_DIR,
    QUALITY_REPORT_FILENAME,
    HTML_REPORT_FILENAME,
)
from src.validator import profile_to_dataframe, build_summary_row

logger = logging.getLogger(__name__)

# ─── Excel color palette ──────────────────────────────────────────────────────
COLOR_PASS   = "C6EFCE"   # light green
COLOR_FAIL   = "FFC7CE"   # light red
COLOR_WARN   = "FFEB9C"   # light yellow
COLOR_HEADER = "1F4E79"   # dark blue
COLOR_WHITE  = "FFFFFF"
COLOR_LIGHT  = "D9E1F2"   # light blue


def generate_quality_report(
    before_profile: Dict[str, Any],
    after_profile:  Dict[str, Any],
    validation_results: List[Dict],
    cleaning_log:   Dict[str, Any],
    metadata:       Dict[str, Any],
) -> Path:
    """
    Write the Excel data-quality report and return its path.
    """
    out_path = REPORTS_DIR / QUALITY_REPORT_FILENAME
    logger.info(f"Generating quality report → {out_path}")

    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Sheet 1: Summary ────────────────────────────────────────────────
        _write_summary_sheet(writer, wb, before_profile, after_profile, metadata)

        # ── Sheet 2 & 3: Column Profiles ────────────────────────────────────
        _write_column_profile(writer, wb, before_profile, "Column Profile - Before")
        _write_column_profile(writer, wb, after_profile,  "Column Profile - After")

        # ── Sheet 4: Validation Results ─────────────────────────────────────
        _write_validation_sheet(writer, wb, validation_results)

        # ── Sheet 5: Cleaning Log ───────────────────────────────────────────
        _write_cleaning_log_sheet(writer, wb, cleaning_log)

    logger.info(f"Quality report saved: {out_path}")

    # Generate HTML report
    html_path = _generate_html_report(
        before_profile, after_profile, validation_results, metadata
    )
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Excel Sheets
# ─────────────────────────────────────────────────────────────────────────────

def _write_summary_sheet(writer, wb, before, after, metadata):
    before_row = build_summary_row(before)
    after_row  = build_summary_row(after)
    df = pd.DataFrame([before_row, after_row])
    df.to_excel(writer, sheet_name="Summary", startrow=6, index=False)

    ws = writer.sheets["Summary"]
    _set_col_widths(ws, df, start_col=0)

    # Header block
    title_fmt = wb.add_format({
        "bold": True, "font_size": 16, "font_color": COLOR_WHITE,
        "bg_color": COLOR_HEADER, "align": "center", "valign": "vcenter",
    })
    meta_fmt = wb.add_format({"font_size": 10, "italic": True})

    ws.merge_range("A1:H1", "Data Cleaning & Quality Report", title_fmt)
    ws.write("A2", f"File: {metadata.get('filename', 'N/A')}", meta_fmt)
    ws.write("A3", f"Rows (raw): {metadata.get('raw_rows', 'N/A'):,}", meta_fmt)
    ws.write("A4", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_fmt)

    # Highlight improvements
    _apply_comparison_colors(wb, writer.sheets["Summary"], df, start_row=6)


def _write_column_profile(writer, wb, profile, sheet_name):
    df = profile_to_dataframe(profile)
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    ws = writer.sheets[sheet_name]
    _write_header_row(wb, ws, df)
    _set_col_widths(ws, df, start_col=0)
    # Color-code Missing % column
    _color_numeric_column(wb, ws, df, "Missing %", threshold=0, reverse=True)


def _write_validation_sheet(writer, wb, results: List[Dict]):
    df = pd.DataFrame(results)
    df.to_excel(writer, sheet_name="Validation Results", index=False)
    ws = writer.sheets["Validation Results"]
    _write_header_row(wb, ws, df)
    _set_col_widths(ws, df, start_col=0)

    pass_fmt = wb.add_format({"bg_color": COLOR_PASS, "bold": True})
    fail_fmt = wb.add_format({"bg_color": COLOR_FAIL, "bold": True})
    warn_fmt = wb.add_format({"bg_color": COLOR_WARN, "bold": True})

    status_col_idx = df.columns.get_loc("Status")
    for row_idx, row in df.iterrows():
        fmt = pass_fmt if row["Status"] == "PASS" else (
              warn_fmt if row["Status"] == "WARN" else fail_fmt)
        ws.write(row_idx + 1, status_col_idx, row["Status"], fmt)


def _write_cleaning_log_sheet(writer, wb, log: Dict):
    rows = []
    rows.append({"Step": "Duplicates Removed",       "Detail": log["duplicates"]["removed"]})
    rows.append({"Step": "Critical Null Rows Dropped","Detail": log["critical_nulls"]["removed"]})
    rows.append({"Step": "Whitespace Cells Fixed",    "Detail": log["whitespace"]["cells_fixed"]})
    for col, cnt in log["negatives"]["columns_fixed"].items():
        rows.append({"Step": f"Negatives Fixed ({col})", "Detail": cnt})
    for col, info in log["missing_fill"]["columns_filled"].items():
        rows.append({"Step": f"Nulls Filled ({col})", "Detail": f"{info['filled']} via {info['strategy']}"})
    for item in log["derived"]["derived"]:
        rows.append({"Step": "Derived Column", "Detail": item})
    for col, cnt in log["outlier_flags"]["outliers_flagged"].items():
        rows.append({"Step": f"Outliers Flagged ({col})", "Detail": cnt})

    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name="Cleaning Log", index=False)
    ws = writer.sheets["Cleaning Log"]
    _write_header_row(wb, ws, df)
    _set_col_widths(ws, df, start_col=0)


# ─────────────────────────────────────────────────────────────────────────────
# HTML Report
# ─────────────────────────────────────────────────────────────────────────────

def _generate_html_report(before, after, validation_results, metadata) -> Path:
    before_df = profile_to_dataframe(before)
    after_df  = profile_to_dataframe(after)
    val_df    = pd.DataFrame(validation_results)

    before_row = build_summary_row(before)
    after_row  = build_summary_row(after)
    summary_df = pd.DataFrame([before_row, after_row])

    improvements = {
        "missing_pct_delta":    round(before["total_missing_pct"] - after["total_missing_pct"], 2),
        "dup_delta":            before["duplicate_rows"] - after["duplicate_rows"],
        "completeness_delta":   round(after["completeness_score"] - before["completeness_score"], 2),
    }

    html = _build_html(
        metadata, summary_df, before_df, after_df, val_df, improvements
    )

    out_path = REPORTS_HTML_DIR / HTML_REPORT_FILENAME
    out_path.write_text(html, encoding="utf-8")
    logger.info(f"HTML report saved: {out_path}")
    return out_path


def _build_html(metadata, summary_df, before_df, after_df, val_df, improvements) -> str:
    def df_to_html(df, classes="table"):
        return df.to_html(index=False, classes=classes, border=0, escape=True)

    status_colors = {"PASS": "#28a745", "FAIL": "#dc3545", "WARN": "#ffc107"}

    val_rows = ""
    for _, row in val_df.iterrows():
        color = status_colors.get(row.get("Status", ""), "#6c757d")
        val_rows += f"""<tr>
            <td>{row.get('Check','')}</td>
            <td style="color:{color};font-weight:bold">{row.get('Status','')}</td>
            <td>{row.get('Count','')}</td>
            <td>{row.get('Detail','')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Quality Report</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f4f6f9; color: #333; }}
  header {{ background: #1F4E79; color: white; padding: 24px 40px; }}
  header h1 {{ margin: 0; font-size: 28px; }}
  header p  {{ margin: 4px 0 0; opacity: .8; font-size: 14px; }}
  .container {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
  .card {{ background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.1);
           padding: 24px; margin-bottom: 28px; }}
  .card h2 {{ margin-top: 0; color: #1F4E79; border-bottom: 2px solid #D9E1F2; padding-bottom: 10px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
  .kpi {{ background: #D9E1F2; border-radius: 8px; padding: 16px; text-align: center; }}
  .kpi .value {{ font-size: 32px; font-weight: bold; color: #1F4E79; }}
  .kpi .label {{ font-size: 13px; color: #555; margin-top: 4px; }}
  .kpi.positive {{ background: #C6EFCE; }} .kpi.positive .value {{ color: #276221; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #1F4E79; color: white; padding: 10px 12px; text-align: left; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #e0e0e0; }}
  tr:nth-child(even) td {{ background: #f9f9f9; }}
  footer {{ text-align: center; color: #999; font-size: 12px; padding: 24px; }}
</style>
</head>
<body>
<header>
  <h1>📊 Data Quality Report</h1>
  <p>File: <strong>{metadata.get('filename','N/A')}</strong> &nbsp;|&nbsp;
     Raw Rows: <strong>{metadata.get('raw_rows',0):,}</strong> &nbsp;|&nbsp;
     Generated: <strong>{datetime.now().strftime('%Y-%m-%d %H:%M')}</strong></p>
</header>
<div class="container">

  <div class="card">
    <h2>🔑 Improvement Highlights</h2>
    <div class="kpi-grid">
      <div class="kpi positive">
        <div class="value">{improvements['missing_pct_delta']}%</div>
        <div class="label">Missing Data Reduced</div>
      </div>
      <div class="kpi positive">
        <div class="value">{improvements['dup_delta']:,}</div>
        <div class="label">Duplicates Removed</div>
      </div>
      <div class="kpi positive">
        <div class="value">+{improvements['completeness_delta']}%</div>
        <div class="label">Completeness Gained</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>📋 Dataset Summary (Before vs After)</h2>
    {df_to_html(summary_df)}
  </div>

  <div class="card">
    <h2>✅ Validation Results</h2>
    <table>
      <thead><tr><th>Check</th><th>Status</th><th>Count</th><th>Detail</th></tr></thead>
      <tbody>{val_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>📊 Column Profile — Before Cleaning</h2>
    {df_to_html(before_df)}
  </div>

  <div class="card">
    <h2>✨ Column Profile — After Cleaning</h2>
    {df_to_html(after_df)}
  </div>

</div>
<footer>Generated by Data Cleaning &amp; Reporting Automation &bull; {datetime.now().year}</footer>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# xlsxwriter helpers
# ─────────────────────────────────────────────────────────────────────────────

def _write_header_row(wb, ws, df: pd.DataFrame, row: int = 0):
    hdr_fmt = wb.add_format({
        "bold": True, "bg_color": COLOR_HEADER, "font_color": COLOR_WHITE,
        "border": 1, "align": "center",
    })
    for col_idx, col_name in enumerate(df.columns):
        ws.write(row, col_idx, col_name, hdr_fmt)


def _set_col_widths(ws, df: pd.DataFrame, start_col: int = 0):
    for col_idx, col in enumerate(df.columns):
        max_len = max(len(str(col)), df[col].astype(str).str.len().max() if len(df) else 0)
        ws.set_column(start_col + col_idx, start_col + col_idx, min(max_len + 4, 40))


def _apply_comparison_colors(wb, ws, df: pd.DataFrame, start_row: int):
    good_fmt = wb.add_format({"bg_color": COLOR_PASS})
    bad_fmt  = wb.add_format({"bg_color": COLOR_FAIL})
    # Row 0 = before (index start_row+1), Row 1 = after (index start_row+2)
    # For numeric columns, highlight improvements in the "After" row
    improve_cols = ["Duplicate Rows", "Duplicate %", "Total Missing Cells", "Missing %"]
    for col in improve_cols:
        if col in df.columns:
            col_idx = df.columns.get_loc(col)
            before_val = df.iloc[0][col]
            after_val  = df.iloc[1][col]
            after_fmt  = good_fmt if after_val <= before_val else bad_fmt
            ws.write(start_row + 1, col_idx, before_val)
            ws.write(start_row + 2, col_idx, after_val, after_fmt)


def _color_numeric_column(wb, ws, df: pd.DataFrame, col_name: str,
                           threshold: float, reverse: bool = False):
    if col_name not in df.columns:
        return
    good_fmt = wb.add_format({"bg_color": COLOR_PASS})
    bad_fmt  = wb.add_format({"bg_color": COLOR_FAIL})
    col_idx = df.columns.get_loc(col_name)
    for row_idx, val in enumerate(df[col_name]):
        try:
            v = float(val)
        except (ValueError, TypeError):
            continue
        fmt = (good_fmt if v <= threshold else bad_fmt) if not reverse else \
              (bad_fmt  if v <= threshold else good_fmt)
        ws.write(row_idx + 1, col_idx, val, fmt)
