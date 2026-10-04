"""
cleaner.py — Core data cleaning engine.

Steps performed (in order):
1. Normalize column names (lowercase, strip spaces, replace spaces with underscores)
2. Drop exact duplicate rows
3. Drop rows where CRITICAL_COLUMNS are null
4. Normalize date columns
5. Strip whitespace from string/object columns
6. Harmonize categories (case + known variant mapping)
7. Fix negative values in non-negative columns
8. Fill remaining missing values per column strategy
9. Derive computed columns (e.g., total_revenue = quantity * unit_price)
10. Flag statistical outliers (adds a boolean column, does NOT drop rows)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

from src.config import (
    CRITICAL_COLUMNS,
    COLUMN_TYPE_MAP,
    DATE_FORMATS,
    OUTPUT_DATE_FORMAT,
    CATEGORY_MAPS,
    OUTLIER_IQR_FACTOR,
    NON_NEGATIVE_COLUMNS,
    FILL_STRATEGY,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Run the full cleaning pipeline on *df*.

    Returns
    -------
    cleaned_df : pd.DataFrame
        The cleaned dataset.
    cleaning_log : dict
        Step-by-step counts of rows/values changed.
    """
    log: Dict = {}
    df = df.copy()

    df, log["col_rename"]     = _normalize_column_names(df)
    df, log["duplicates"]     = _remove_duplicates(df)
    df, log["critical_nulls"] = _drop_critical_nulls(df)
    df, log["dates"]          = _normalize_dates(df)
    df, log["whitespace"]     = _strip_whitespace(df)
    df, log["categories"]     = _harmonize_categories(df)
    df, log["negatives"]      = _fix_negatives(df)
    df, log["missing_fill"]   = _fill_missing(df)
    df, log["derived"]        = _derive_columns(df)
    df, log["outlier_flags"]  = _flag_outliers(df)

    logger.info("Cleaning complete.")
    _log_summary(log)
    return df, log


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Column names
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_column_names(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    original = list(df.columns)
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-]+", "_", regex=True)
        .str.replace(r"[^\w]", "", regex=True)
    )
    renamed = {o: n for o, n in zip(original, df.columns) if o != n}
    if renamed:
        logger.debug(f"Renamed columns: {renamed}")
    return df, {"renamed": renamed}


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Duplicates
# ─────────────────────────────────────────────────────────────────────────────

def _remove_duplicates(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    logger.info(f"Duplicates removed: {removed:,}")
    return df, {"removed": removed}


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Critical nulls
# ─────────────────────────────────────────────────────────────────────────────

def _drop_critical_nulls(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    before = len(df)
    existing_critical = [c for c in CRITICAL_COLUMNS if c in df.columns]
    df = df.dropna(subset=existing_critical)
    removed = before - len(df)
    logger.info(f"Rows dropped (critical null): {removed:,}")
    return df, {"removed": removed, "columns_checked": existing_critical}


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Date normalization
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_dates(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    date_cols = [
        col for col, typ in COLUMN_TYPE_MAP.items()
        if typ == "date" and col in df.columns
    ]
    fixed = {}
    for col in date_cols:
        series = df[col].copy()
        parsed = _parse_dates(series)
        failed = parsed.isnull().sum() - series.isnull().sum()
        df[col] = parsed.dt.strftime(OUTPUT_DATE_FORMAT).where(parsed.notna(), other=None)
        fixed[col] = int(parsed.notna().sum())
        if failed > 0:
            logger.warning(f"  '{col}': {failed} values could not be parsed as dates.")
    return df, {"columns_fixed": fixed}


def _parse_dates(series: pd.Series) -> pd.Series:
    """Try pandas infer first, then explicit formats."""
    # First pass: let pandas infer
    parsed = pd.to_datetime(series, errors="coerce")
    mask_failed = parsed.isnull() & series.notna()

    if mask_failed.any():
        for fmt in DATE_FORMATS:
            still_failed = parsed.isnull() & series.notna()
            if not still_failed.any():
                break
            attempt = pd.to_datetime(
                series[still_failed], format=fmt, errors="coerce"
            )
            parsed[still_failed] = attempt
    return parsed


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Whitespace
# ─────────────────────────────────────────────────────────────────────────────

def _strip_whitespace(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    obj_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    count = 0
    for col in obj_cols:
        before = df[col].copy()
        df[col] = df[col].astype(str).str.strip().replace("nan", np.nan)
        changed = (df[col] != before).sum()
        count += int(changed)
    logger.info(f"Whitespace fixed in {count:,} cells across {len(obj_cols)} columns.")
    return df, {"cells_fixed": count, "columns": obj_cols}


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Category harmonization
# ─────────────────────────────────────────────────────────────────────────────

def _harmonize_categories(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    results = {}
    for col, mapping in CATEGORY_MAPS.items():
        if col not in df.columns:
            continue
        before = df[col].copy()
        # Lowercase for lookup, then apply map, fall back to title-casing original
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.lower()
            .map(lambda v: mapping.get(v, None))
            .fillna(before.astype(str).str.strip().str.title())
        )
        # Restore NaN where original was NaN
        df.loc[before.isnull(), col] = np.nan
        changed = int((df[col] != before).sum())
        results[col] = changed
        logger.debug(f"  '{col}': {changed} values harmonized.")
    return df, {"columns_harmonized": results}


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Negative values
# ─────────────────────────────────────────────────────────────────────────────

def _fix_negatives(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    results = {}
    for col in NON_NEGATIVE_COLUMNS:
        if col not in df.columns:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
        neg_mask = df[col] < 0
        count = int(neg_mask.sum())
        df.loc[neg_mask, col] = np.nan   # treat as missing; will be filled next
        results[col] = count
        if count:
            logger.warning(f"  '{col}': {count} negative values → set to NaN.")
    return df, {"columns_fixed": results}


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Fill missing values
# ─────────────────────────────────────────────────────────────────────────────

def _fill_missing(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    results = {}
    for col, strategy in FILL_STRATEGY.items():
        if col not in df.columns:
            continue
        if strategy == "derived":
            continue   # handled in step 9
        missing_before = int(df[col].isnull().sum())
        if missing_before == 0:
            continue

        if strategy == "median":
            df[col] = pd.to_numeric(df[col], errors="coerce")
            fill_val = df[col].median()
            df[col] = df[col].fillna(fill_val)
        elif strategy == "mode":
            fill_val = df[col].mode().iloc[0] if not df[col].mode().empty else "Unknown"
            df[col] = df[col].fillna(fill_val)
        else:  # literal string e.g. "Unknown"
            df[col] = df[col].fillna(strategy)

        filled = missing_before - int(df[col].isnull().sum())
        results[col] = {"strategy": strategy, "filled": filled}
        logger.debug(f"  '{col}': {filled} nulls filled with strategy='{strategy}'.")
    return df, {"columns_filled": results}


# ─────────────────────────────────────────────────────────────────────────────
# Step 9 — Derived columns
# ─────────────────────────────────────────────────────────────────────────────

def _derive_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    derived = []

    # total_revenue = quantity * unit_price (if both exist)
    if "total_revenue" in df.columns and "quantity" in df.columns and "unit_price" in df.columns:
        mask = df["total_revenue"].isnull()
        df.loc[mask, "total_revenue"] = (
            pd.to_numeric(df.loc[mask, "quantity"], errors="coerce") *
            pd.to_numeric(df.loc[mask, "unit_price"], errors="coerce")
        )
        derived.append(f"total_revenue: {int(mask.sum())} values computed")

    # Ensure numeric types
    for col in ["quantity", "unit_price", "total_revenue"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Add derived time columns (useful for Power BI)
    if "order_date" in df.columns:
        dt = pd.to_datetime(df["order_date"], errors="coerce")
        df["order_year"]  = dt.dt.year.astype("Int64")
        df["order_month"] = dt.dt.month.astype("Int64")
        df["order_month_name"] = dt.dt.strftime("%B")
        df["order_quarter"] = dt.dt.quarter.astype("Int64")
        derived.append("order_year, order_month, order_month_name, order_quarter added")

    logger.info(f"Derived columns: {derived}")
    return df, {"derived": derived}


# ─────────────────────────────────────────────────────────────────────────────
# Step 10 — Outlier flagging
# ─────────────────────────────────────────────────────────────────────────────

def _flag_outliers(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    numeric_cols = [
        col for col in df.select_dtypes(include=[np.number]).columns
        if col in COLUMN_TYPE_MAP and COLUMN_TYPE_MAP[col] == "numeric"
    ]
    flag_counts = {}
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 4:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - OUTLIER_IQR_FACTOR * iqr, q3 + OUTLIER_IQR_FACTOR * iqr
        flag_col = f"{col}_outlier"
        df[flag_col] = ((df[col] < lower) | (df[col] > upper)).fillna(False)
        count = int(df[flag_col].sum())
        flag_counts[col] = count
        if count:
            logger.debug(f"  '{col}': {count} outliers flagged in '{flag_col}'.")
    return df, {"outliers_flagged": flag_counts}


# ─────────────────────────────────────────────────────────────────────────────
# Logging helper
# ─────────────────────────────────────────────────────────────────────────────

def _log_summary(log: dict) -> None:
    logger.info("─" * 50)
    logger.info("Cleaning Summary:")
    logger.info(f"  Duplicates removed   : {log['duplicates']['removed']:,}")
    logger.info(f"  Critical null drops  : {log['critical_nulls']['removed']:,}")
    logger.info(f"  Whitespace fixes     : {log['whitespace']['cells_fixed']:,} cells")
    logger.info(f"  Negatives set to NaN : {sum(log['negatives']['columns_fixed'].values()):,}")
    total_filled = sum(v["filled"] for v in log["missing_fill"]["columns_filled"].values())
    logger.info(f"  Missing values filled: {total_filled:,}")
    logger.info("─" * 50)
