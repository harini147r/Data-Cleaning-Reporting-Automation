"""
generate_sample_data.py — Creates a realistic synthetic sales dataset with
intentional data quality issues for demonstration and testing.

Run: python generate_sample_data.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

OUTPUT_PATH = Path(__file__).parent / "data" / "sample" / "sample_sales_data.csv"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

N_ROWS = 1200

# ─── Reference data ───────────────────────────────────────────────────────────
CUSTOMER_NAMES = [
    "Alice Johnson", "bob smith", "CAROL DAVIS", "  David Lee  ",
    "Emma Wilson", "Frank Thomas", "Grace Martinez", "henry brown",
    "Isabella Clark", "JAMES WHITE", "Karen Harris", "liam jackson",
    "Mia Thompson", "Noah Garcia", "Olivia Lewis", "peter hall",
    "Quinn Walker", "Rachel Allen", "samuel young", "Tina King",
    "Uma Scott", "Victor Green", "Wendy Baker", "XAVIER NELSON",
    "Yara Carter", "Zoe Mitchell",
]

# Intentionally mixed-case and abbreviated categories
CATEGORIES_RAW = [
    "Electronics", "electronics", "ELECTRONICS", "elec",
    "Clothing", "clothing", "CLOTHING", "cloth",
    "Furniture", "furniture", "furn",
    "Sports", "sports", "sport",
    "Books", "books", "book",
    "Toys", "toys", "toy",
    "Food & Beverage", "food", "food & bev",
]

PRODUCTS = {
    "Electronics": ["Laptop Pro 15", "Wireless Headphones", "Smart Watch", "USB-C Hub", "Gaming Mouse"],
    "Clothing":    ["Winter Jacket", "Running Shoes", "Denim Jeans", "Polo Shirt", "Yoga Pants"],
    "Furniture":   ["Office Chair", "Standing Desk", "Bookshelf", "Coffee Table", "Filing Cabinet"],
    "Sports":      ["Yoga Mat", "Resistance Bands", "Protein Shaker", "Jump Rope", "Foam Roller"],
    "Books":       ["Python Data Science", "Clean Code", "The Pragmatic Programmer", "SQL Cookbook", "ML Fundamentals"],
    "Toys":        ["LEGO Classic Set", "Puzzle 1000pc", "Board Game Deluxe", "RC Car", "Art Kit"],
    "Food & Beverage": ["Organic Coffee 1kg", "Green Tea Box", "Protein Bar Pack", "Granola Mix", "Coconut Oil"],
}

# Intentionally mixed-case regions
REGIONS_RAW = [
    "North", "north", "NORTH", "n",
    "South", "south", "SOUTH", "s",
    "East", "east", "EAST", "e",
    "West", "west", "WEST", "w",
]

# Mixed-case statuses
STATUSES_RAW = [
    "Completed", "completed", "COMPLETED", "Complete", "done",
    "Pending", "pending", "PENDING", "pend",
    "Cancelled", "cancelled", "CANCELLED", "canceled", "cancel",
    "Returned", "returned", "RETURNED",
]

# Three different date formats mixed
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%b %d %Y"]

START_DATE = datetime(2023, 1, 1)
END_DATE   = datetime(2024, 12, 31)


def random_date() -> str:
    delta = (END_DATE - START_DATE).days
    d = START_DATE + timedelta(days=random.randint(0, delta))
    fmt = random.choice(DATE_FORMATS)
    return d.strftime(fmt)


def generate() -> pd.DataFrame:
    rows = []
    order_ids = [f"ORD-{str(i).zfill(5)}" for i in range(1, N_ROWS + 1)]

    # Add ~30 duplicate order IDs
    dup_ids = random.sample(order_ids[:500], 30)
    order_ids.extend(dup_ids)
    random.shuffle(order_ids)
    order_ids = order_ids[:N_ROWS]

    for i, order_id in enumerate(order_ids):
        category_raw = random.choice(CATEGORIES_RAW)
        # Map to canonical for product lookup
        cat_canonical = _canonical_category(category_raw)
        products_list = PRODUCTS.get(cat_canonical, ["Generic Product"])
        product_name = random.choice(products_list)

        # Add whitespace to some product names
        if random.random() < 0.05:
            product_name = "  " + product_name + "  "

        quantity = random.randint(1, 20)
        unit_price = round(random.uniform(5.0, 1500.0), 2)
        total_revenue = round(quantity * unit_price, 2)

        row = {
            "order_id":         order_id,
            "customer_name":    random.choice(CUSTOMER_NAMES),
            "order_date":       random_date(),
            "region":           random.choice(REGIONS_RAW),
            "product_category": category_raw,
            "product_name":     product_name,
            "quantity":         quantity,
            "unit_price":       unit_price,
            "total_revenue":    total_revenue,
            "status":           random.choice(STATUSES_RAW),
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # ── Inject quality issues ─────────────────────────────────────────────────

    # 1. Missing values
    for col, pct in [
        ("customer_name", 0.02),
        ("order_date",    0.02),
        ("region",        0.04),
        ("product_category", 0.03),
        ("quantity",      0.05),
        ("unit_price",    0.04),
        ("total_revenue", 0.06),
        ("status",        0.03),
    ]:
        mask = np.random.random(len(df)) < pct
        df.loc[mask, col] = np.nan

    # 2. Negative values in numeric columns
    neg_indices = random.sample(range(len(df)), 25)
    df.loc[neg_indices[:12], "quantity"]      = -abs(df.loc[neg_indices[:12], "quantity"])
    df.loc[neg_indices[12:], "unit_price"]    = -abs(df.loc[neg_indices[12:], "unit_price"])

    # 3. Extreme outliers
    outlier_indices = random.sample(range(len(df)), 10)
    df.loc[outlier_indices[:5], "unit_price"]    = round(random.uniform(50000, 99999), 2)
    df.loc[outlier_indices[5:], "total_revenue"] = round(random.uniform(100000, 500000), 2)

    # 4. Missing order_id in a few rows (will be dropped)
    df.loc[random.sample(range(len(df)), 5), "order_id"] = np.nan

    # Shuffle rows
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


def _canonical_category(raw: str) -> str:
    mapping = {
        "elec": "Electronics", "electronics": "Electronics", "electronic": "Electronics",
        "cloth": "Clothing",   "clothes": "Clothing",        "clothing": "Clothing",
        "furn": "Furniture",   "furniture": "Furniture",
        "sport": "Sports",     "sports": "Sports",
        "food": "Food & Beverage", "food & bev": "Food & Beverage",
        "book": "Books",       "books": "Books",
        "toy": "Toys",         "toys": "Toys",
    }
    return mapping.get(raw.lower().strip(), raw.strip().title())


if __name__ == "__main__":
    df = generate()
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"[OK] Sample dataset saved -> {OUTPUT_PATH}")
    print(f"   Rows: {len(df):,}  |  Columns: {len(df.columns)}")
    print(f"   Missing values injected, duplicates injected, outliers injected.")
    print(f"\n   Quality issues summary:")
    print(f"   - Duplicates : ~30 rows")
    print(f"   - Missing    : ~{int(df.isnull().sum().sum())} cells")
    print(f"   - Negatives  : ~25 values")
    print(f"   - Outliers   : ~10 extreme values")
    print(f"   - Date formats: 3 different formats mixed")
    print(f"   - Case issues : categories, regions, statuses all have mixed casing")
