"""
exporter.py — Output writers.

Writes:
1. Cleaned CSV  → data/cleaned/cleaned_data.csv
2. Cleaned Excel (formatted) → data/cleaned/cleaned_data.xlsx
3. Business metrics Excel → reports/business_metrics.xlsx
4. Power BI export (multi-sheet) → powerbi/dashboard_data.xlsx
5. SQLite database → data/cleaned/business_data.db  (if SQLITE_ENABLED)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any
import logging
from datetime import datetime

from src.config import (
    DATA_CLEANED_DIR,
    REPORTS_DIR,
    POWERBI_DIR,
    CLEANED_CSV_FILENAME,
    CLEANED_EXCEL_FILENAME,
    METRICS_REPORT_FILENAME,
    POWERBI_EXPORT_FILENAME,
    SQLITE_ENABLED,
    SQLITE_DB_PATH,
    SQLITE_TABLE,
)

# ── colour constants (duplicated from reporter to avoid circular import) ──────
_HDR_COLOR   = "1F4E79"
_WHITE       = "FFFFFF"
_LIGHT_BLUE  = "D9E1F2"

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def export_all(
    cleaned_df: pd.DataFrame,
    metrics:    Dict[str, Any],
    metadata:   Dict[str, Any],
) -> Dict[str, Path]:
    """
    Export all outputs.

    Returns a dict mapping output_name → file_path.
    """
    paths = {}

    paths["cleaned_csv"]   = _write_csv(cleaned_df)
    paths["cleaned_excel"] = _write_cleaned_excel(cleaned_df, metadata)
    paths["metrics_excel"] = _write_metrics_excel(metrics, metadata)
    paths["powerbi_excel"] = _write_powerbi_export(cleaned_df, metrics, metadata)

    if SQLITE_ENABLED:
        paths["sqlite_db"] = _write_sqlite(cleaned_df)

    logger.info("All exports complete.")
    for name, path in paths.items():
        logger.info(f"  {name:<20} → {path}")
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# 1. Cleaned CSV
# ─────────────────────────────────────────────────────────────────────────────

def _write_csv(df: pd.DataFrame) -> Path:
    path = DATA_CLEANED_DIR / CLEANED_CSV_FILENAME
    df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info(f"Cleaned CSV: {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cleaned Excel (formatted)
# ─────────────────────────────────────────────────────────────────────────────

def _write_cleaned_excel(df: pd.DataFrame, metadata: Dict) -> Path:
    path = DATA_CLEANED_DIR / CLEANED_EXCEL_FILENAME
    safe_df = _sanitize_df(df)
    with pd.ExcelWriter(path, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:
        safe_df.to_excel(writer, sheet_name="Cleaned Data", index=False)
        wb = writer.book
        ws = writer.sheets["Cleaned Data"]
        _apply_table_style(wb, ws, safe_df, sheet_name="Cleaned Data")

    logger.info(f"Cleaned Excel: {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# 3. Business Metrics Excel
# ─────────────────────────────────────────────────────────────────────────────

def _write_metrics_excel(metrics: Dict[str, Any], metadata: Dict) -> Path:
    path = REPORTS_DIR / METRICS_REPORT_FILENAME
    with pd.ExcelWriter(path, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:
        wb = writer.book

        # ── Summary KPIs ─────────────────────────────────────────────────────
        summary = metrics.get("summary", {})
        summary_df = pd.DataFrame(
            [{"Metric": k, "Value": v} for k, v in summary.items()]
        )
        summary_df.to_excel(writer, sheet_name="KPI Summary", index=False)
        ws = writer.sheets["KPI Summary"]
        _apply_table_style(wb, ws, summary_df, sheet_name="KPI Summary")
        _add_title(wb, ws, "Key Business Metrics", metadata)

        # ── Monthly Trend ─────────────────────────────────────────────────────
        monthly = metrics.get("monthly_trend")
        if monthly is not None and not monthly.empty:
            monthly.to_excel(writer, sheet_name="Monthly Trend", index=False)
            ws = writer.sheets["Monthly Trend"]
            _apply_table_style(wb, ws, monthly, sheet_name="Monthly Trend")
            _add_line_chart(wb, ws, monthly, writer)

        # ── Category Breakdown ────────────────────────────────────────────────
        cat = metrics.get("category_breakdown")
        if cat is not None and not cat.empty:
            cat.to_excel(writer, sheet_name="Category Breakdown", index=False)
            ws = writer.sheets["Category Breakdown"]
            _apply_table_style(wb, ws, cat, sheet_name="Category Breakdown")

        # ── Region Breakdown ──────────────────────────────────────────────────
        reg = metrics.get("region_breakdown")
        if reg is not None and not reg.empty:
            reg.to_excel(writer, sheet_name="Region Breakdown", index=False)
            ws = writer.sheets["Region Breakdown"]
            _apply_table_style(wb, ws, reg, sheet_name="Region Breakdown")

        # ── Status Breakdown ──────────────────────────────────────────────────
        status = metrics.get("status_breakdown")
        if status is not None and not status.empty:
            status.to_excel(writer, sheet_name="Status Breakdown", index=False)
            ws = writer.sheets["Status Breakdown"]
            _apply_table_style(wb, ws, status, sheet_name="Status Breakdown")

        # ── Top Products ──────────────────────────────────────────────────────
        top = metrics.get("top_products")
        if top is not None and not top.empty:
            top.to_excel(writer, sheet_name="Top Products", index=False)
            ws = writer.sheets["Top Products"]
            _apply_table_style(wb, ws, top, sheet_name="Top Products")

    logger.info(f"Metrics Excel: {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# 4. Power BI Export
# ─────────────────────────────────────────────────────────────────────────────

def _write_powerbi_export(
    df: pd.DataFrame,
    metrics: Dict[str, Any],
    metadata: Dict
) -> Path:
    path = POWERBI_DIR / POWERBI_EXPORT_FILENAME
    safe_df = _sanitize_df(df)
    with pd.ExcelWriter(path, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}}) as writer:

        # Sheet 1: Full cleaned dataset
        safe_df.to_excel(writer, sheet_name="CleanedData", index=False)

        # Sheet 2: Summary metrics (as key-value pairs for card visuals)
        summary = metrics.get("summary", {})
        summary_df = pd.DataFrame(
            [{"Metric": k, "Value": v} for k, v in summary.items()]
        )
        summary_df.to_excel(writer, sheet_name="MetricsSummary", index=False)

        # Sheet 3: Monthly trend
        monthly = metrics.get("monthly_trend")
        if monthly is not None and not monthly.empty:
            monthly.to_excel(writer, sheet_name="MonthlyTrend", index=False)

        # Sheet 4: Category breakdown
        cat = metrics.get("category_breakdown")
        if cat is not None and not cat.empty:
            cat.to_excel(writer, sheet_name="CategoryBreakdown", index=False)

        # Sheet 5: Region breakdown
        reg = metrics.get("region_breakdown")
        if reg is not None and not reg.empty:
            reg.to_excel(writer, sheet_name="RegionBreakdown", index=False)

        # Sheet 6: Status breakdown
        status = metrics.get("status_breakdown")
        if status is not None and not status.empty:
            status.to_excel(writer, sheet_name="StatusBreakdown", index=False)

    logger.info(f"Power BI export: {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# 5. SQLite
# ─────────────────────────────────────────────────────────────────────────────

def _write_sqlite(df: pd.DataFrame) -> Path:
    import sqlite3
    path = SQLITE_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert Int64 (nullable int) to standard int64 for SQLite compatibility
    df_sql = df.copy()
    for col in df_sql.columns:
        if pd.api.types.is_extension_array_dtype(df_sql[col]):
            df_sql[col] = df_sql[col].astype(object)

    conn = sqlite3.connect(str(path))
    df_sql.to_sql(SQLITE_TABLE, conn, if_exists="replace", index=False)
    conn.close()
    logger.info(f"SQLite DB: {path}  (table: {SQLITE_TABLE})")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _apply_table_style(wb, ws, df: pd.DataFrame, sheet_name: str):
    hdr_fmt = wb.add_format({
        "bold": True, "bg_color": _HDR_COLOR, "font_color": _WHITE,
        "border": 1, "align": "center", "valign": "vcenter",
    })
    alt_fmt = wb.add_format({"bg_color": _LIGHT_BLUE})

    for col_idx, col_name in enumerate(df.columns):
        ws.write(0, col_idx, col_name, hdr_fmt)
        max_len = max(len(str(col_name)),
                      df[col_name].astype(str).str.len().max() if len(df) else 0)
        ws.set_column(col_idx, col_idx, min(max_len + 4, 45))

    for row_idx in range(len(df)):
        if row_idx % 2 == 1:
            for col_idx in range(len(df.columns)):
                val = df.iloc[row_idx, col_idx]
                # Sanitize NaN / inf so xlsxwriter doesn't raise TypeError
                val = _sanitize_cell(val)
                ws.write(row_idx + 1, col_idx, val, alt_fmt)

    ws.freeze_panes(1, 0)


def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare DataFrame for Excel export by converting nullable types and handling infinities."""
    clean_df = df.copy()
    for col in clean_df.columns:
        if pd.api.types.is_extension_array_dtype(clean_df[col]):
            clean_df[col] = clean_df[col].astype(object)
    return clean_df


def _sanitize_cell(val):
    """Convert NaN/inf/NA values to empty string for safe Excel writing."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
        if isinstance(val, (float, np.floating)):
            if np.isneginf(val) or np.isposinf(val) or np.isnan(val):
                return ""
    except (TypeError, ValueError):
        pass
    return val


def _add_title(wb, ws, title: str, metadata: Dict):
    # Insert 2 rows at top for title — xlsxwriter doesn't support row insertion,
    # so we write the title at row 0 and shift data by using startrow offset.
    # (The table is already written at row=0 via to_excel; we add a text box.)
    title_fmt = wb.add_format({
        "bold": True, "font_size": 14, "font_color": _WHITE,
        "bg_color": _HDR_COLOR, "align": "left", "valign": "vcenter",
    })
    ws.write("D1", f"  {title} — {metadata.get('filename','')}", title_fmt)


def _add_line_chart(wb, ws, df: pd.DataFrame, writer):
    """Add a line chart to the Monthly Trend sheet if revenue column exists."""
    if "total_revenue" not in df.columns:
        return
    chart = wb.add_chart({"type": "line"})
    n_rows = len(df)
    col_idx = df.columns.get_loc("total_revenue")
    chart.add_series({
        "name":       "Monthly Revenue",
        "categories": ["Monthly Trend", 1, 0, n_rows, 0],   # Month col
        "values":     ["Monthly Trend", 1, col_idx, n_rows, col_idx],
        "line":       {"color": "#1F4E79", "width": 2.5},
        "marker":     {"type": "circle", "fill": {"color": "#4472C4"}},
    })
    chart.set_title({"name": "Monthly Revenue Trend"})
    chart.set_x_axis({"name": "Month"})
    chart.set_y_axis({"name": "Revenue (\$)"})
    chart.set_size({"width": 600, "height": 320})
    chart.set_style(10)
    ws.insert_chart("H2", chart)
