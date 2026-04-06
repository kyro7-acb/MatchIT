"""
services/preprocess.py
-----------------------
Deterministic, ML-free normalization layer.

Responsibilities:
  • Lowercase strings
  • Remove special characters / punctuation
  • Strip vendor stop-words
  • Normalize invoice / reference numbers
  • Parse dates → datetime
  • Parse amounts → float

This layer is called after extract.py and BEFORE similarity.py.
Clean input → reliable matching.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from config import VENDOR_STOPWORDS
from utils import get_logger, parse_amount, parse_date

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# String normalization
# ---------------------------------------------------------------------------

def normalize_string(text: Optional[str]) -> str:
    """
    Full normalization pipeline for a text field:
      1. Lowercase
      2. Remove special characters (keep alphanumeric + spaces)
      3. Collapse multiple spaces / strip
    """
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)   # remove punctuation, symbols
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_reference(text: Optional[str]) -> str:
    """
    Normalize invoice / ledger reference numbers.
    Strips spaces, hyphens, slashes — keeps alphanumeric only.
    """
    if not text:
        return ""
    cleaned = text.upper()
    cleaned = re.sub(r"[\s\-/]", "", cleaned)  # remove separators
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    return cleaned


def normalize_vendor(text: Optional[str]) -> str:
    """
    Normalize a vendor / supplier name:
      1. Standard string normalization
      2. Remove legal-entity stop-words (pvt, ltd, inc, …)
      3. Collapse whitespace
    """
    base = normalize_string(text)
    tokens = base.split()
    filtered = [t for t in tokens if t not in VENDOR_STOPWORDS]
    return " ".join(filtered).strip()


# ---------------------------------------------------------------------------
# Invoice normalization
# ---------------------------------------------------------------------------

def preprocess_invoice(invoice: dict) -> dict:
    """
    Normalize a raw invoice dict produced by extract.py.

    Input keys  : invoice_number, vendor_name, date, amount
    Output adds : normalized_invoice_number, normalized_vendor,
                  parsed_date (datetime | None), parsed_amount (float | None)

    The original raw fields are preserved for auditability.
    """
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


# ---------------------------------------------------------------------------
# Ledger row normalization
# ---------------------------------------------------------------------------

def preprocess_ledger_entry(entry: dict) -> dict:
    """
    Normalize a raw ledger row dict.

    Input keys  : reference, vendor, date, debit, credit
    Output adds : normalized_reference, normalized_vendor,
                  parsed_date, debit_amount (float | None),
                  credit_amount (float | None)
    """
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


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def preprocess_invoices(invoices: list[dict]) -> list[dict]:
    """Normalize a list of raw invoice dicts."""
    return [preprocess_invoice(inv) for inv in invoices]


def preprocess_ledger(entries: list[dict]) -> list[dict]:
    """Normalize a list of raw ledger entry dicts."""
    return [preprocess_ledger_entry(e) for e in entries]
