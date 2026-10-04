"""
standardizer.py — Post-cleaning validation & conformance checks.

After cleaning, this module re-examines the dataframe and returns a
structured pass/fail validation report ensuring the clean data
meets all expected quality standards.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

from src.config import (
    CRITICAL_COLUMNS,
    COLUMN_TYPE_MAP,
    NON_NEGATIVE_COLUMNS,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when cleaned data fails a critical validation rule."""
    pass


def validate(df: pd.DataFrame) -> Tuple[bool, List[Dict]]:
    """
    Run post-cleaning validation checks on *df*.

    Returns
    -------
    passed : bool
        True if all CRITICAL checks pass.
    results : list of dict
        One entry per check with keys:
        - check_name, status ("PASS" / "FAIL" / "WARN"), detail, count
    """
    results: List[Dict] = []
    critical_failure = False

    # ── Check 1: No nulls in critical columns ─────────────────────────────
    existing_critical = [c for c in CRITICAL_COLUMNS if c in df.columns]
    for col in existing_critical:
        null_count = int(df[col].isnull().sum())
        status = "PASS" if null_count == 0 else "FAIL"
        if status == "FAIL":
            critical_failure = True
        results.append({
            "Check":   f"No nulls in critical column '{col}'",
            "Status":  status,
            "Count":   null_count,
            "Detail":  f"{null_count} null values remain" if null_count else "OK",
        })

    # ── Check 2: No duplicate rows ────────────────────────────────────────
    dup_count = int(df.duplicated().sum())
    results.append({
        "Check":  "No duplicate rows",
        "Status": "PASS" if dup_count == 0 else "WARN",
        "Count":  dup_count,
        "Detail": f"{dup_count} duplicates remain" if dup_count else "OK",
    })

    # ── Check 3: Non-negative columns ────────────────────────────────────
    for col in NON_NEGATIVE_COLUMNS:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        neg_count = int((series < 0).sum())
        results.append({
            "Check":  f"No negatives in '{col}'",
            "Status": "PASS" if neg_count == 0 else "WARN",
            "Count":  neg_count,
            "Detail": f"{neg_count} negative values" if neg_count else "OK",
        })

    # ── Check 4: Numeric column type conformance ──────────────────────────
    for col, expected_type in COLUMN_TYPE_MAP.items():
        if col not in df.columns or expected_type != "numeric":
            continue
        non_numeric = pd.to_numeric(df[col], errors="coerce").isnull().sum()
        null_count = df[col].isnull().sum()
        type_issues = int(non_numeric - null_count)
        results.append({
            "Check":  f"Numeric type conformance '{col}'",
            "Status": "PASS" if type_issues == 0 else "WARN",
            "Count":  type_issues,
            "Detail": f"{type_issues} non-numeric values" if type_issues else "OK",
        })

    # ── Check 5: Date column conformance ──────────────────────────────────
    for col, expected_type in COLUMN_TYPE_MAP.items():
        if col not in df.columns or expected_type != "date":
            continue
        parsed = pd.to_datetime(df[col], errors="coerce")
        null_before = int(df[col].isnull().sum())
        null_after = int(parsed.isnull().sum())
        parse_fails = max(0, null_after - null_before)
        results.append({
            "Check":  f"Date format conformance '{col}'",
            "Status": "PASS" if parse_fails == 0 else "WARN",
            "Count":  parse_fails,
            "Detail": f"{parse_fails} unparseable dates" if parse_fails else "OK",
        })

    # ── Check 6: Overall completeness ────────────────────────────────────
    completeness = round((1 - df.isnull().mean().mean()) * 100, 2)
    results.append({
        "Check":  "Overall completeness ≥ 90%",
        "Status": "PASS" if completeness >= 90 else "WARN",
        "Count":  completeness,
        "Detail": f"{completeness}% complete",
    })

    passed = not critical_failure
    _log_results(results)
    return passed, results


def _log_results(results: List[Dict]) -> None:
    logger.info("Post-cleaning validation:")
    for r in results:
        icon = "✔" if r["Status"] == "PASS" else ("⚠" if r["Status"] == "WARN" else "✘")
        logger.info(f"  [{r['Status']}] {icon} {r['Check']} — {r['Detail']}")
