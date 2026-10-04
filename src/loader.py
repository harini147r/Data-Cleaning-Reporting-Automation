"""
loader.py — File ingestion module.

Supports .csv and .xlsx / .xls files.
Auto-detects format from file extension.
Returns a raw pandas DataFrame plus load metadata.
"""

import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def load_file(filepath: str | Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load a CSV or Excel file into a pandas DataFrame.

    Parameters
    ----------
    filepath : str or Path
        Path to the input file.

    Returns
    -------
    df : pd.DataFrame
        Raw loaded data.
    metadata : dict
        Load statistics — filename, extension, row/col counts, file size.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file extension is not supported.
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    logger.info(f"Loading file: {path.name}  ({ext})")

    if ext == ".csv":
        df = _load_csv(path)
    else:
        df = _load_excel(path)

    metadata = {
        "filename":   path.name,
        "extension":  ext,
        "filepath":   str(path.resolve()),
        "file_size_kb": round(path.stat().st_size / 1024, 2),
        "raw_rows":   len(df),
        "raw_cols":   len(df.columns),
        "columns":    list(df.columns),
    }

    logger.info(
        f"Loaded {metadata['raw_rows']:,} rows × {metadata['raw_cols']} columns "
        f"from '{path.name}' ({metadata['file_size_kb']} KB)"
    )
    return df, metadata


def _load_csv(path: Path) -> pd.DataFrame:
    """Try common encodings when loading a CSV."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc, low_memory=False)
            logger.debug(f"CSV loaded with encoding: {enc}")
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode '{path.name}' with any supported encoding.")


def _load_excel(path: Path) -> pd.DataFrame:
    """Load the first sheet of an Excel workbook."""
    try:
        df = pd.read_excel(path, sheet_name=0, engine=_excel_engine(path))
        return df
    except Exception as exc:
        raise ValueError(f"Failed to read Excel file '{path.name}': {exc}") from exc


def _excel_engine(path: Path) -> str:
    return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"


def get_latest_raw_file(raw_dir: Path) -> Path:
    """
    Return the most recently modified supported file in *raw_dir*.

    Useful when no explicit --input argument is given.
    """
    candidates = [
        f for f in raw_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No supported data files found in '{raw_dir}'. "
            "Place a .csv or .xlsx file in data/raw/ and try again."
        )
    latest = max(candidates, key=lambda f: f.stat().st_mtime)
    logger.info(f"Auto-selected latest raw file: {latest.name}")
    return latest
