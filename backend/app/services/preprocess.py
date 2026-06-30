from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from config import VENDOR_STOPWORDS
from utils import get_logger

logger = get_logger(__name__)


# String normalization by transitioning strings into lowercase, removing special characters and strip spaces
def normalize_string(text: Optional[str]) -> str:
    
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)   # remove punctuation, symbols
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_reference(text: Optional[str]) -> str:
    
    if not text:
        return ""
    cleaned = text.upper()
    cleaned = re.sub(r"[\s\-/]", "", cleaned)  # remove separators
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    return cleaned


def normalize_vendor(text: Optional[str]) -> str:
    
    base = normalize_string(text)
    tokens = base.split()
    filtered = [t for t in tokens if t not in VENDOR_STOPWORDS]
    return " ".join(filtered).strip()

# Date parsing
_DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
    "%d.%m.%Y", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
    "%b %d %Y",  "%B %d %Y",
    "%d/%m/%y",  "%m/%d/%y",
]

def parse_date(date_str: str) -> Optional[datetime]:
    
    if not date_str:
        return None
    cleaned = re.sub(r"\s+", " ", date_str.strip().rstrip(","))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None

# Amount parsing
def parse_amount(amount_str: str) -> Optional[float]:
    
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

# Invoice normalization
def preprocess_invoice(invoice: dict) -> dict:
    
    result = dict(invoice)  # shallow copy; don't mutate caller's dict

    raw_invoice_no = invoice.get("invoice_number") or ""
    raw_vendor     = invoice.get("vendor_name")    or ""
    raw_date       = invoice.get("date")           or ""
    raw_amount     = invoice.get("amount")         or ""

    result["normalized_invoice_number"] = normalize_reference(raw_invoice_no)
    result["normalized_vendor"]         = normalize_vendor(raw_vendor)
    result["parsed_date"]               = parse_date(raw_date)
    result["parsed_amount"]             = parse_amount(raw_amount)

    logger.debug(
        "Preprocessed invoice: inv_no=%s vendor=%s date=%s amount=%s",
        result["normalized_invoice_number"],
        result["normalized_vendor"],
        result["parsed_date"],
        result["parsed_amount"],
    )
    return result

# Ledger row normalization
def preprocess_ledger_entry(entry: dict) -> dict:
    
    result = dict(entry)

    result["normalized_reference"] = normalize_reference(entry.get("reference") or "")
    result["normalized_vendor"]    = normalize_vendor(entry.get("vendor") or "")
    result["parsed_date"]          = parse_date(entry.get("date") or "")
    result["debit_amount"]         = parse_amount(entry.get("debit") or "")
    result["credit_amount"]        = parse_amount(entry.get("credit") or "")

    logger.debug(
        "Preprocessed ledger: ref=%s vendor=%s date=%s debit=%s credit=%s",
        result["normalized_reference"],
        result["normalized_vendor"],
        result["parsed_date"],
        result["debit_amount"],
        result["credit_amount"],
    )
    return result

# Batch helpers

def preprocess_invoices(invoices: list[dict]) -> list[dict]:
    """Normalize a list of raw invoice dicts."""
    return [preprocess_invoice(inv) for inv in invoices]

def preprocess_ledger(entries: list[dict]) -> list[dict]:
    """Normalize a list of raw ledger entry dicts."""
    return [preprocess_ledger_entry(e) for e in entries]
