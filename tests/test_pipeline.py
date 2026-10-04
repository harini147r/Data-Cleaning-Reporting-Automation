"""
tests/test_pipeline.py — Unit and integration tests for the automation pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src import loader, validator, cleaner, standardizer, metrics, exporter
from src.config import DATA_SAMPLE_DIR


@pytest.fixture
def sample_raw_data():
    df = pd.DataFrame({
        "order_id": ["ORD-1", "ORD-2", "ORD-2", "ORD-3", None],
        "customer_name": ["Alice ", "  bob", "  bob", "Carol", "Dave"],
        "order_date": ["2023-01-15", "15/01/2023", "15/01/2023", "Jan 16 2023", "2023-01-17"],
        "region": ["north", "South", "South", "e", "w"],
        "product_category": ["elec", "Clothing", "Clothing", "furn", "Books"],
        "product_name": ["  Laptop  ", "Shirt", "Shirt", "Desk", "Python"],
        "quantity": [2, -5, -5, 4, None],
        "unit_price": [500.0, 30.0, 30.0, None, 15.0],
        "total_revenue": [1000.0, None, None, None, None],
        "status": ["completed", "PENDING", "PENDING", "canceled", "Completed"],
    })
    return df


def test_validator_profile(sample_raw_data):
    profile = validator.profile_dataframe(sample_raw_data, label="Test Raw")
    assert profile["total_rows"] == 5
    assert profile["duplicate_rows"] == 1
    assert profile["total_missing_cells"] > 0
    assert "order_id" in profile["columns"]


def test_cleaner_pipeline(sample_raw_data):
    clean_df, log = cleaner.clean(sample_raw_data)

    # Null order_id row should be dropped + duplicate ORD-2 removed
    assert len(clean_df) == 3
    # Check deduplication
    assert clean_df.duplicated().sum() == 0
    # Check negative quantity was fixed
    assert (clean_df["quantity"] < 0).sum() == 0
    # Check category harmonization
    assert "Electronics" in clean_df["product_category"].values
    assert "Furniture" in clean_df["product_category"].values
    # Check status harmonization
    assert "Cancelled" in clean_df["status"].values
    # Check whitespace stripped
    assert clean_df["customer_name"].iloc[0] == "Alice"
    assert clean_df["product_name"].iloc[0] == "Laptop"


def test_standardizer_validation(sample_raw_data):
    clean_df, _ = cleaner.clean(sample_raw_data)
    passed, results = standardizer.validate(clean_df)
    assert passed is True
    assert all(r["Status"] in ("PASS", "WARN") for r in results)


def test_business_metrics(sample_raw_data):
    clean_df, _ = cleaner.clean(sample_raw_data)
    biz_metrics = metrics.compute_metrics(clean_df)
    assert "summary" in biz_metrics
    assert biz_metrics["summary"]["Total Records"] == len(clean_df)
    assert biz_metrics["summary"]["Total Revenue"] > 0
    assert not biz_metrics["monthly_trend"].empty
