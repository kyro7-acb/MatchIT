"""
utils.py
--------
Shared utility functions used across the matching pipeline.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from config import LOG_LEVEL


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a consistently-configured logger."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=level,
    )
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
    "%d.%m.%Y", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
    "%b %d %Y",  "%B %d %Y",
    "%d/%m/%y",  "%m/%d/%y",
]


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Try multiple date formats and return a datetime object, or None on failure.
    Strips extraneous whitespace/punctuation before parsing.
    """
    if not date_str:
        return None
    cleaned = re.sub(r"\s+", " ", date_str.strip().rstrip(","))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

def parse_amount(amount_str: str) -> Optional[float]:
    """
    Convert a raw amount string like '1,23,456.78' or '$45.00' to a float.
    Returns None if parsing fails.
    """
    if not amount_str:
        return None
    # Remove currency symbols and thousands separators
    cleaned = re.sub(r"[^\d.]", "", str(amount_str))
    # Handle multiple dots (keep only last as decimal point)
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Console table printer
# ---------------------------------------------------------------------------

def print_match_table(results: list[dict]) -> None:
    """
    Print a human-readable table of match results to stdout.
    """
    if not results:
        print("No results to display.")
        return

    headers = ["Invoice ID", "Ledger Ref", "Score", "Status"]
    col_widths = [max(len(h), 12) for h in headers]

    # Adjust widths based on data
    for r in results:
        col_widths[0] = max(col_widths[0], len(str(r.get("invoice_id", ""))))
        col_widths[1] = max(col_widths[1], len(str(r.get("ledger_ref", ""))))
        col_widths[2] = max(col_widths[2], 6)
        col_widths[3] = max(col_widths[3], len(str(r.get("status", ""))))

    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"

    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for r in results:
        score_str = f"{r.get('score', 0):.4f}"
        print(fmt.format(
            str(r.get("invoice_id", "N/A")),
            str(r.get("ledger_ref", "N/A")),
            score_str,
            str(r.get("status", "N/A")),
        ))
    print(sep)
