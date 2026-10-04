"""
config.py — Central configuration for the Data Cleaning & Reporting Automation pipeline.

Edit this file to adapt the pipeline to a new dataset without touching any logic.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────
# Project Root & Directory Paths
# ─────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_RAW_DIR      = ROOT_DIR / "data" / "raw"
DATA_CLEANED_DIR  = ROOT_DIR / "data" / "cleaned"
DATA_SAMPLE_DIR   = ROOT_DIR / "data" / "sample"
REPORTS_DIR       = ROOT_DIR / "reports"
REPORTS_HTML_DIR  = ROOT_DIR / "reports" / "html"
POWERBI_DIR       = ROOT_DIR / "powerbi"

# Ensure output directories exist
for _dir in [DATA_RAW_DIR, DATA_CLEANED_DIR, DATA_SAMPLE_DIR,
             REPORTS_DIR, REPORTS_HTML_DIR, POWERBI_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# Column Configuration
# ─────────────────────────────────────────────

# Columns where a null value means the row should be DROPPED entirely
CRITICAL_COLUMNS = ["order_id", "customer_name", "order_date"]

# Expected data types per column  (used for validation)
# Supported values: "string", "numeric", "date", "category"
COLUMN_TYPE_MAP = {
    "order_id":          "string",
    "customer_name":     "string",
    "order_date":        "date",
    "region":            "category",
    "product_category":  "category",
    "product_name":      "string",
    "quantity":          "numeric",
    "unit_price":        "numeric",
    "total_revenue":     "numeric",
    "status":            "category",
}

# ─────────────────────────────────────────────
# Date Parsing
# ─────────────────────────────────────────────
DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%B %d %Y",       # January 15 2024
    "%b %d %Y",       # Jan 15 2024
    "%d %B %Y",
    "%Y/%m/%d",
]

OUTPUT_DATE_FORMAT = "%Y-%m-%d"

# ─────────────────────────────────────────────
# Category Harmonization Maps
# Maps known raw variants → canonical values
# ─────────────────────────────────────────────
CATEGORY_MAPS = {
    "product_category": {
        "elec":          "Electronics",
        "electronics":   "Electronics",
        "electronic":    "Electronics",
        "cloth":         "Clothing",
        "clothes":       "Clothing",
        "clothing":      "Clothing",
        "furn":          "Furniture",
        "furniture":     "Furniture",
        "sport":         "Sports",
        "sports":        "Sports",
        "food":          "Food & Beverage",
        "food & bev":    "Food & Beverage",
        "book":          "Books",
        "books":         "Books",
        "toy":           "Toys",
        "toys":          "Toys",
    },
    "region": {
        "n":      "North",
        "north":  "North",
        "s":      "South",
        "south":  "South",
        "e":      "East",
        "east":   "East",
        "w":      "West",
        "west":   "West",
    },
    "status": {
        "completed":   "Completed",
        "complete":    "Completed",
        "done":        "Completed",
        "pending":     "Pending",
        "pend":        "Pending",
        "cancelled":   "Cancelled",
        "canceled":    "Cancelled",
        "cancel":      "Cancelled",
        "returned":    "Returned",
        "return":      "Returned",
    },
}

# ─────────────────────────────────────────────
# Numeric Outlier Detection
# ─────────────────────────────────────────────
# Uses Interquartile Range (IQR) method
# Values beyond (Q1 - FACTOR*IQR, Q3 + FACTOR*IQR) are flagged as outliers
OUTLIER_IQR_FACTOR = 3.0

# Columns where negative values are invalid
NON_NEGATIVE_COLUMNS = ["quantity", "unit_price", "total_revenue"]

# ─────────────────────────────────────────────
# Missing Value Fill Strategy
# "median"  → fill with column median  (numeric columns)
# "mode"    → fill with most frequent  (categorical columns)
# "Unknown" → fill with literal string (string/category columns)
# "zero"    → fill with 0
# ─────────────────────────────────────────────
FILL_STRATEGY = {
    "quantity":          "median",
    "unit_price":        "median",
    "total_revenue":     "derived",   # will be recomputed from quantity * unit_price
    "region":            "Unknown",
    "product_category":  "Unknown",
    "status":            "Unknown",
    "product_name":      "Unknown",
}

# ─────────────────────────────────────────────
# Business Metrics
# ─────────────────────────────────────────────
REVENUE_COLUMN   = "total_revenue"
DATE_COLUMN      = "order_date"
CATEGORY_COLUMN  = "product_category"
REGION_COLUMN    = "region"
QUANTITY_COLUMN  = "quantity"
STATUS_COLUMN    = "status"
TOP_N_CATEGORIES = 5

# ─────────────────────────────────────────────
# Report Settings
# ─────────────────────────────────────────────
QUALITY_REPORT_FILENAME  = "data_quality_report.xlsx"
METRICS_REPORT_FILENAME  = "business_metrics.xlsx"
HTML_REPORT_FILENAME     = "quality_report.html"
CLEANED_CSV_FILENAME     = "cleaned_data.csv"
CLEANED_EXCEL_FILENAME   = "cleaned_data.xlsx"
POWERBI_EXPORT_FILENAME  = "dashboard_data.xlsx"

# ─────────────────────────────────────────────
# SQLite (optional)
# ─────────────────────────────────────────────
SQLITE_ENABLED  = True
SQLITE_DB_PATH  = ROOT_DIR / "data" / "cleaned" / "business_data.db"
SQLITE_TABLE    = "cleaned_sales"
