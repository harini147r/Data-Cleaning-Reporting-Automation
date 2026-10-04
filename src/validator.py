"""
validator.py — Pre- and post-cleaning data quality profiler.

Produces a structured quality snapshot used by reporter.py to build
the before/after comparison.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

from src.config import (
    COLUMN_TYPE_MAP,
    DATE_FORMATS,
    NON_NEGATIVE_COLUMNS,
    OUTLIER_IQR_FACTOR,
)

logger = logging.getLogger(__name__)


def profile_dataframe(df: pd.DataFrame, label: str = "snapshot") -> Dict[str, Any]:
    """
    Generate a comprehensive quality profile of *df*.

    Returns a dict with:
    - summary stats per column
    - duplicate counts
    - type conformance issues
    - date format inconsistencies
    - outlier flags
    """
    logger.info(f"Profiling dataframe [{label}]: {len(df):,} rows × {len(df.columns)} cols")

    profile: Dict[str, Any] = {
        "label":        label,
        "total_rows":   len(df),
        "total_cols":   len(df.columns),
        "columns":      {},
        "duplicate_rows":          int(df.duplicated().sum()),
        "duplicate_rows_pct":      round(df.duplicated().mean() * 100, 2),
        "total_missing_cells":     int(df.isnull().sum().sum()),
        "total_missing_pct":       round(df.isnull().mean().mean() * 100, 2),
        "completeness_score":      round((1 - df.isnull().mean().mean()) * 100, 2),
    }

    for col in df.columns:
        series = df[col]
        col_info: Dict[str, Any] = {
            "dtype":          str(series.dtype),
            "missing_count":  int(series.isnull().sum()),
            "missing_pct":    round(series.isnull().mean() * 100, 2),
            "unique_count":   int(series.nunique(dropna=True)),
        }

        # Numeric stats
        if pd.api.types.is_numeric_dtype(series):
            col_info.update(_numeric_stats(series))

        # Category / string stats
        elif pd.api.types.is_object_dtype(series) or isinstance(series.dtype, pd.CategoricalDtype) or pd.api.types.is_string_dtype(series):
            col_info.update(_categorical_stats(series))

        # Date stats
        if pd.api.types.is_datetime64_any_dtype(series):
            col_info.update(_date_stats(series))

        # Type conformance check
        expected_type = COLUMN_TYPE_MAP.get(col)
        if expected_type:
            col_info["expected_type"] = expected_type
            col_info["type_issues"] = _check_type_issues(series, expected_type)
        else:
            col_info["expected_type"] = "unknown"
            col_info["type_issues"] = 0

        # Outlier check for numeric cols
        if pd.api.types.is_numeric_dtype(series) and expected_type == "numeric":
            col_info["outlier_count"] = _count_outliers(series)

        profile["columns"][col] = col_info

    return profile


def _numeric_stats(series: pd.Series) -> Dict[str, Any]:
    clean = series.dropna()
    if clean.empty:
        return {"min": None, "max": None, "mean": None, "median": None, "std": None,
                "negative_count": 0}
    return {
        "min":            round(float(clean.min()), 4),
        "max":            round(float(clean.max()), 4),
        "mean":           round(float(clean.mean()), 4),
        "median":         round(float(clean.median()), 4),
        "std":            round(float(clean.std()), 4),
        "negative_count": int((clean < 0).sum()),
    }


def _categorical_stats(series: pd.Series) -> Dict[str, Any]:
    clean = series.dropna()
    top_values = clean.value_counts().head(5).to_dict()
    # Detect whitespace issues
    has_leading_trailing = int(
        clean.astype(str).apply(lambda x: x != x.strip()).sum()
    )
    # Detect mixed case for same semantic value
    lower_unique = clean.astype(str).str.lower().nunique()
    actual_unique = clean.astype(str).nunique()
    case_inconsistencies = max(0, actual_unique - lower_unique)

    return {
        "top_values":          top_values,
        "whitespace_issues":   has_leading_trailing,
        "case_inconsistencies": case_inconsistencies,
    }


def _date_stats(series: pd.Series) -> Dict[str, Any]:
    clean = series.dropna()
    if clean.empty:
        return {"date_min": None, "date_max": None, "date_range_days": None}
    return {
        "date_min":       str(clean.min().date()),
        "date_max":       str(clean.max().date()),
        "date_range_days": (clean.max() - clean.min()).days,
    }


def _check_type_issues(series: pd.Series, expected: str) -> int:
    """Return count of values that don't conform to the expected type."""
    clean = series.dropna()
    if clean.empty:
        return 0

    if expected == "numeric":
        try:
            pd.to_numeric(clean, errors="raise")
            return 0
        except (ValueError, TypeError):
            return int(pd.to_numeric(clean, errors="coerce").isnull().sum())

    if expected == "date":
        parsed = pd.to_datetime(clean, errors="coerce")
        return int(parsed.isnull().sum())

    # string / category — all values are technically valid strings
    return 0


def _count_outliers(series: pd.Series) -> int:
    """Count outliers using the IQR method."""
    clean = series.dropna()
    if len(clean) < 4:
        return 0
    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
    iqr = q3 - q1
    factor = OUTLIER_IQR_FACTOR
    lower, upper = q1 - factor * iqr, q3 + factor * iqr
    return int(((clean < lower) | (clean > upper)).sum())


def profile_to_dataframe(profile: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert a profile dict into a flat DataFrame for reporting.
    One row per column.
    """
    rows = []
    for col, info in profile["columns"].items():
        row = {
            "Column":            col,
            "Expected Type":     info.get("expected_type", ""),
            "Actual Dtype":      info.get("dtype", ""),
            "Missing Count":     info.get("missing_count", 0),
            "Missing %":         info.get("missing_pct", 0),
            "Unique Values":     info.get("unique_count", 0),
            "Type Issues":       info.get("type_issues", 0),
            "Outlier Count":     info.get("outlier_count", 0),
            "Whitespace Issues": info.get("whitespace_issues", 0),
            "Case Issues":       info.get("case_inconsistencies", 0),
            "Negative Count":    info.get("negative_count", 0),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def build_summary_row(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return a one-row summary dict for the dataset-level comparison."""
    return {
        "Snapshot":               profile["label"],
        "Total Rows":             profile["total_rows"],
        "Duplicate Rows":         profile["duplicate_rows"],
        "Duplicate %":            profile["duplicate_rows_pct"],
        "Total Missing Cells":    profile["total_missing_cells"],
        "Missing %":              profile["total_missing_pct"],
        "Completeness Score (%)": profile["completeness_score"],
    }
