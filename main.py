"""
main.py — Entry point for the Data Cleaning & Reporting Automation pipeline.

Usage:
    python main.py                              # auto-picks latest file in data/raw/
    python main.py --input data/raw/myfile.csv  # specific file
    python main.py --input data/sample/sample_sales_data.csv
    python main.py --input data/raw/myfile.xlsx --report-only
    python main.py --input data/raw/myfile.csv --output-dir data/cleaned/custom/

Pipeline:
    Raw File → Load → Validate (before) → Clean → Validate (after)
             → Metrics → Quality Report → Business Metrics → Export
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 output on Windows consoles (for emoji/unicode in print statements)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Colorama for pretty console output ───────────────────────────────────────
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = CYAN = YELLOW = RED = WHITE = MAGENTA = ""
    class Style:
        BRIGHT = RESET_ALL = ""

# ─── Project imports ──────────────────────────────────────────────────────────
from src.config import DATA_RAW_DIR, DATA_SAMPLE_DIR
from src import loader, validator, cleaner, standardizer, metrics, reporter, exporter


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("pipeline.log", mode="a", encoding="utf-8"),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Banner & step helpers
# ─────────────────────────────────────────────────────────────────────────────

def _banner() -> None:
    line = "═" * 62
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{line}")
    print("  📊  Data Cleaning & Reporting Automation Pipeline")
    print(f"  🕐  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{line}{Style.RESET_ALL}\n")


def _step(n: int, title: str) -> float:
    print(f"{Fore.YELLOW}{Style.BRIGHT}[Step {n}] {title}{Style.RESET_ALL}")
    return time.time()


def _done(t0: float) -> None:
    elapsed = time.time() - t0
    print(f"         {Fore.GREEN}✔ Done  ({elapsed:.2f}s){Style.RESET_ALL}\n")


def _section(title: str) -> None:
    print(f"\n{Fore.CYAN}{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}{Style.RESET_ALL}")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(input_path: Path, report_only: bool = False) -> None:
    logger = logging.getLogger(__name__)
    total_start = time.time()

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    t0 = _step(1, "Loading raw data file...")
    raw_df, metadata = loader.load_file(input_path)
    _done(t0)

    print(f"         File   : {metadata['filename']}")
    print(f"         Size   : {metadata['file_size_kb']} KB")
    print(f"         Shape  : {metadata['raw_rows']:,} rows × {metadata['raw_cols']} columns")
    print(f"         Columns: {', '.join(metadata['columns'][:6])}{'...' if len(metadata['columns']) > 6 else ''}\n")

    # ── Step 2: Pre-cleaning profile ─────────────────────────────────────────
    t0 = _step(2, "Profiling raw data quality...")
    before_profile = validator.profile_dataframe(raw_df, label="Before Cleaning")
    _done(t0)

    _print_quick_stats(before_profile, "RAW DATA QUALITY")

    if report_only:
        _section("Report-Only Mode — Skipping cleaning")
        _generate_report_only(raw_df, before_profile, metadata)
        return

    # ── Step 3: Clean ─────────────────────────────────────────────────────────
    t0 = _step(3, "Cleaning data...")
    cleaned_df, cleaning_log = cleaner.clean(raw_df)
    _done(t0)

    print(f"         Rows after cleaning: {len(cleaned_df):,}")
    print(f"         Columns: {len(cleaned_df.columns)}\n")

    # ── Step 4: Post-cleaning profile ─────────────────────────────────────────
    t0 = _step(4, "Validating cleaned data...")
    after_profile = validator.profile_dataframe(cleaned_df, label="After Cleaning")
    passed, val_results = standardizer.validate(cleaned_df)
    _done(t0)

    _print_quick_stats(after_profile, "CLEANED DATA QUALITY")
    _print_validation_summary(val_results, passed)

    # ── Step 5: Metrics ───────────────────────────────────────────────────────
    t0 = _step(5, "Computing business metrics...")
    biz_metrics = metrics.compute_metrics(cleaned_df)
    _done(t0)

    _print_metrics_summary(biz_metrics["summary"])

    # ── Step 6: Quality Report ────────────────────────────────────────────────
    t0 = _step(6, "Generating data quality report...")
    report_path = reporter.generate_quality_report(
        before_profile, after_profile, val_results, cleaning_log, metadata
    )
    _done(t0)

    # ── Step 7: Export ────────────────────────────────────────────────────────
    t0 = _step(7, "Exporting all outputs...")
    export_paths = exporter.export_all(cleaned_df, biz_metrics, metadata)
    _done(t0)

    # ── Final Summary ─────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    _print_final_summary(report_path, export_paths, total_elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# Console print helpers
# ─────────────────────────────────────────────────────────────────────────────

def _print_quick_stats(profile: dict, title: str) -> None:
    _section(title)
    print(f"  Total Rows         : {profile['total_rows']:,}")
    print(f"  Duplicate Rows     : {profile['duplicate_rows']:,}  ({profile['duplicate_rows_pct']}%)")
    print(f"  Missing Cells      : {profile['total_missing_cells']:,}  ({profile['total_missing_pct']}%)")
    print(f"  Completeness Score : {profile['completeness_score']}%")
    print()


def _print_validation_summary(results: list, passed: bool) -> None:
    _section("VALIDATION RESULTS")
    status_map = {
        "PASS": f"{Fore.GREEN}PASS{Style.RESET_ALL}",
        "WARN": f"{Fore.YELLOW}WARN{Style.RESET_ALL}",
        "FAIL": f"{Fore.RED}FAIL{Style.RESET_ALL}",
    }
    for r in results:
        icon  = "✔" if r["Status"] == "PASS" else ("⚠" if r["Status"] == "WARN" else "✘")
        color_status = status_map.get(r["Status"], r["Status"])
        print(f"  [{color_status}] {icon}  {r['Check']:<45}  {r['Detail']}")

    overall = f"{Fore.GREEN}ALL CRITICAL CHECKS PASSED ✔" if passed else f"{Fore.RED}CRITICAL CHECKS FAILED ✘"
    print(f"\n  Overall: {Style.BRIGHT}{overall}{Style.RESET_ALL}\n")


def _print_metrics_summary(summary: dict) -> None:
    _section("KEY BUSINESS METRICS")
    for k, v in list(summary.items())[:10]:
        if isinstance(v, float):
            print(f"  {k:<30} {v:,.2f}")
        elif isinstance(v, int):
            print(f"  {k:<30} {v:,}")
        else:
            print(f"  {k:<30} {v}")
    print()


def _print_final_summary(report_path: Path, export_paths: dict, elapsed: float) -> None:
    _section("✅ PIPELINE COMPLETE")
    print(f"  Total time: {elapsed:.2f}s\n")
    print(f"  {Fore.GREEN}Output Files:{Style.RESET_ALL}")
    print(f"  📄  Quality Report  : {report_path}")
    for name, path in export_paths.items():
        icons = {
            "cleaned_csv":   "📊",
            "cleaned_excel": "📗",
            "metrics_excel": "📈",
            "powerbi_excel": "⚡",
            "sqlite_db":     "🗄️",
        }
        icon = icons.get(name, "📁")
        print(f"  {icon}  {name:<18}: {path}")
    print()
    print(f"  {Fore.CYAN}Power BI:{Style.RESET_ALL}")
    print(f"  Open Power BI Desktop → Get Data → Excel →")
    print(f"  Select '{export_paths.get('powerbi_excel', 'powerbi/dashboard_data.xlsx')}'")
    print(f"  Connect all 6 sheets for full dashboard coverage.\n")


def _generate_report_only(df, before_profile, metadata):
    """Generate a quality report without cleaning."""
    import copy
    _, val_results = standardizer.validate(df)
    # Dummy cleaning log
    dummy_log = {
        "duplicates":    {"removed": 0},
        "critical_nulls":{"removed": 0},
        "whitespace":    {"cells_fixed": 0},
        "negatives":     {"columns_fixed": {}},
        "missing_fill":  {"columns_filled": {}},
        "derived":       {"derived": []},
        "outlier_flags": {"outliers_flagged": {}},
    }
    reporter.generate_quality_report(
        before_profile, before_profile, val_results, dummy_log, metadata
    )
    print(f"\n{Fore.GREEN}Report generated in reports/ directory.{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Data Cleaning & Reporting Automation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --input data/sample/sample_sales_data.csv
  python main.py --input data/raw/q4_sales.xlsx
  python main.py --input data/raw/q4_sales.xlsx --report-only
  python main.py --input data/raw/q4_sales.xlsx --verbose
        """,
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="Path to the input CSV or Excel file. "
             "If not specified, uses the most recently modified file in data/raw/.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip cleaning — only profile and report on the raw data.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    _setup_logging(verbose=args.verbose)
    _banner()

    logger = logging.getLogger(__name__)

    # Resolve input file
    if args.input:
        input_path = Path(args.input)
    else:
        # Try data/raw/ first, fall back to data/sample/
        try:
            input_path = loader.get_latest_raw_file(DATA_RAW_DIR)
        except FileNotFoundError:
            logger.warning("No files in data/raw/ — using sample dataset.")
            input_path = DATA_SAMPLE_DIR / "sample_sales_data.csv"
            if not input_path.exists():
                logger.error(
                    "Sample dataset not found. "
                    "Run 'python generate_sample_data.py' first, "
                    "then place your file in data/raw/ and re-run."
                )
                sys.exit(1)

    logger.info(f"Input: {input_path.resolve()}")

    try:
        run_pipeline(input_path, report_only=args.report_only)
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Data error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
