"""
metrics.py — Business metrics computation.

Computes key KPIs from the cleaned dataset.
Adapts to whichever configured columns are present.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from src.config import (
    REVENUE_COLUMN,
    DATE_COLUMN,
    CATEGORY_COLUMN,
    REGION_COLUMN,
    QUANTITY_COLUMN,
    STATUS_COLUMN,
    TOP_N_CATEGORIES,
)

logger = logging.getLogger(__name__)


def compute_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute all business metrics from the cleaned dataframe.

    Returns a dict with keys:
    - summary        → high-level KPI dict (for cards)
    - monthly_trend  → DataFrame (month, revenue, orders)
    - category_breakdown → DataFrame (category, revenue, orders, avg_order_value)
    - region_breakdown   → DataFrame (region, revenue, orders)
    - status_breakdown   → DataFrame (status, count, pct)
    - top_products       → DataFrame (product_name, revenue)
    """
    metrics: Dict[str, Any] = {}

    metrics["summary"]            = _compute_summary(df)
    metrics["monthly_trend"]      = _monthly_trend(df)
    metrics["category_breakdown"] = _category_breakdown(df)
    metrics["region_breakdown"]   = _region_breakdown(df)
    metrics["status_breakdown"]   = _status_breakdown(df)
    metrics["top_products"]       = _top_products(df)

    logger.info("Business metrics computed successfully.")
    _log_summary(metrics["summary"])
    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# Summary KPIs
# ─────────────────────────────────────────────────────────────────────────────

def _compute_summary(df: pd.DataFrame) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "Total Records":    len(df),
        "Total Columns":    len(df.columns),
    }

    # Revenue
    if REVENUE_COLUMN in df.columns:
        rev = pd.to_numeric(df[REVENUE_COLUMN], errors="coerce")
        summary["Total Revenue"]        = round(float(rev.sum()), 2)
        summary["Avg Order Value"]      = round(float(rev.mean()), 2)
        summary["Max Order Value"]      = round(float(rev.max()), 2)
        summary["Min Order Value"]      = round(float(rev.min()), 2)

    # Quantity
    if QUANTITY_COLUMN in df.columns:
        qty = pd.to_numeric(df[QUANTITY_COLUMN], errors="coerce")
        summary["Total Units Sold"] = int(qty.sum())
        summary["Avg Units per Order"] = round(float(qty.mean()), 2)

    # Date range
    if DATE_COLUMN in df.columns:
        dates = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
        summary["Date From"] = str(dates.min().date()) if dates.notna().any() else "N/A"
        summary["Date To"]   = str(dates.max().date()) if dates.notna().any() else "N/A"
        summary["Days Covered"] = (dates.max() - dates.min()).days if dates.notna().any() else 0

    # Categories & regions
    if CATEGORY_COLUMN in df.columns:
        summary["Unique Categories"] = int(df[CATEGORY_COLUMN].nunique())
    if REGION_COLUMN in df.columns:
        summary["Unique Regions"] = int(df[REGION_COLUMN].nunique())

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Monthly Trend
# ─────────────────────────────────────────────────────────────────────────────

def _monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    if DATE_COLUMN not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    work["_date"] = pd.to_datetime(work[DATE_COLUMN], errors="coerce")
    work["_period"] = work["_date"].dt.to_period("M")

    agg = {"_period": "count"}
    if REVENUE_COLUMN in work.columns:
        work[REVENUE_COLUMN] = pd.to_numeric(work[REVENUE_COLUMN], errors="coerce")
        agg[REVENUE_COLUMN] = "sum"
    if QUANTITY_COLUMN in work.columns:
        work[QUANTITY_COLUMN] = pd.to_numeric(work[QUANTITY_COLUMN], errors="coerce")
        agg[QUANTITY_COLUMN] = "sum"

    group = work.groupby("_period").agg(
        Orders=("_period", "count"),
        **({REVENUE_COLUMN: pd.NamedAgg(column=REVENUE_COLUMN, aggfunc="sum")}
           if REVENUE_COLUMN in work.columns else {}),
        **({QUANTITY_COLUMN: pd.NamedAgg(column=QUANTITY_COLUMN, aggfunc="sum")}
           if QUANTITY_COLUMN in work.columns else {}),
    ).reset_index()

    group["_period"] = group["_period"].astype(str)
    group.rename(columns={"_period": "Month"}, inplace=True)
    group.sort_values("Month", inplace=True)

    # Month-over-month revenue growth %
    if REVENUE_COLUMN in group.columns:
        group["Revenue_Growth_%"] = group[REVENUE_COLUMN].pct_change().mul(100).round(2)

    return group


# ─────────────────────────────────────────────────────────────────────────────
# Category Breakdown
# ─────────────────────────────────────────────────────────────────────────────

def _category_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    if CATEGORY_COLUMN not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    if REVENUE_COLUMN in work.columns:
        work[REVENUE_COLUMN] = pd.to_numeric(work[REVENUE_COLUMN], errors="coerce")
    if QUANTITY_COLUMN in work.columns:
        work[QUANTITY_COLUMN] = pd.to_numeric(work[QUANTITY_COLUMN], errors="coerce")

    agg_dict = {"Orders": (CATEGORY_COLUMN, "count")}
    if REVENUE_COLUMN in work.columns:
        agg_dict["Total Revenue"] = (REVENUE_COLUMN, "sum")
    if QUANTITY_COLUMN in work.columns:
        agg_dict["Total Units"]   = (QUANTITY_COLUMN, "sum")

    group = work.groupby(CATEGORY_COLUMN).agg(**agg_dict).reset_index()
    group.rename(columns={CATEGORY_COLUMN: "Category"}, inplace=True)

    if "Total Revenue" in group.columns:
        group["Avg Order Value"] = (group["Total Revenue"] / group["Orders"]).round(2)
        group["Revenue Share %"] = (group["Total Revenue"] / group["Total Revenue"].sum() * 100).round(2)
        group.sort_values("Total Revenue", ascending=False, inplace=True)

    return group.head(TOP_N_CATEGORIES + 10)  # return all, Top-N handled in reports


# ─────────────────────────────────────────────────────────────────────────────
# Region Breakdown
# ─────────────────────────────────────────────────────────────────────────────

def _region_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    if REGION_COLUMN not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    if REVENUE_COLUMN in work.columns:
        work[REVENUE_COLUMN] = pd.to_numeric(work[REVENUE_COLUMN], errors="coerce")

    agg_dict = {"Orders": (REGION_COLUMN, "count")}
    if REVENUE_COLUMN in work.columns:
        agg_dict["Total Revenue"] = (REVENUE_COLUMN, "sum")

    group = work.groupby(REGION_COLUMN).agg(**agg_dict).reset_index()
    group.rename(columns={REGION_COLUMN: "Region"}, inplace=True)

    if "Total Revenue" in group.columns:
        group["Revenue Share %"] = (group["Total Revenue"] / group["Total Revenue"].sum() * 100).round(2)
        group.sort_values("Total Revenue", ascending=False, inplace=True)

    return group


# ─────────────────────────────────────────────────────────────────────────────
# Status Breakdown
# ─────────────────────────────────────────────────────────────────────────────

def _status_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    if STATUS_COLUMN not in df.columns:
        return pd.DataFrame()

    counts = df[STATUS_COLUMN].value_counts().reset_index()
    counts.columns = ["Status", "Count"]
    counts["Percentage %"] = (counts["Count"] / counts["Count"].sum() * 100).round(2)
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Top Products
# ─────────────────────────────────────────────────────────────────────────────

def _top_products(df: pd.DataFrame) -> pd.DataFrame:
    if "product_name" not in df.columns or REVENUE_COLUMN not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    work[REVENUE_COLUMN] = pd.to_numeric(work[REVENUE_COLUMN], errors="coerce")

    group = (
        work.groupby("product_name")
        .agg(
            Orders=(REVENUE_COLUMN, "count"),
            Total_Revenue=(REVENUE_COLUMN, "sum"),
        )
        .reset_index()
        .rename(columns={"product_name": "Product"})
        .sort_values("Total_Revenue", ascending=False)
        .head(TOP_N_CATEGORIES)
    )
    return group


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def _log_summary(summary: Dict[str, Any]) -> None:
    logger.info("Key Metrics:")
    for k, v in summary.items():
        logger.info(f"  {k:<30} {v}")
