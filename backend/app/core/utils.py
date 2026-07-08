import logging
import re
from datetime import datetime
from typing import Optional

from app.core.config import WEIGHTS


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    return logging.getLogger(name)


_DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
    "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%y", "%m/%d/%y",
    "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    "%b %d %Y", "%B %d %Y",
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


def parse_amount(amount_str: str) -> Optional[float]:
    if not amount_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(amount_str))
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def compute_field_breakdown(invoice: dict, ledger: dict) -> dict:
    """
    Returns per-field similarity scores AND weighted contributions. Used to build the explainability payload.
    """
    from app.services.similarity import (
        levenshtein_similarity, jaro_winkler,
        date_similarity, amount_similarity,
    )

    s_inv = levenshtein_similarity(
        invoice.get("normalized_invoice_number", ""),
        ledger.get("normalized_reference", ""),
    )
    s_ven = jaro_winkler(
        invoice.get("normalized_vendor", ""),
        ledger.get("normalized_vendor", ""),
    )
    ledger_amount = ledger.get("debit_amount") or ledger.get("credit_amount")
    s_date = date_similarity(invoice.get("parsed_date"), ledger.get("parsed_date"))
    s_amt  = amount_similarity(invoice.get("parsed_amount"), ledger_amount)

    w = WEIGHTS
    def _stringify(value: object) -> str:
        return "" if value is None else str(value)

    return {
        "invoice_number": {
            "score": round(s_inv, 4),
            "weight": w["invoice_number"],
            "contribution": round(s_inv * w["invoice_number"], 4),
            "invoice_value": _stringify(invoice.get("invoice_number")),
            "ledger_value":  _stringify(ledger.get("reference")),
        },
        "vendor": {
            "score": round(s_ven, 4),
            "weight": w["vendor"],
            "contribution": round(s_ven * w["vendor"], 4),
            "invoice_value": _stringify(invoice.get("vendor_name")),
            "ledger_value":  _stringify(ledger.get("vendor")),
        },
        "date": {
            "score": round(s_date, 4),
            "weight": w["date"],
            "contribution": round(s_date * w["date"], 4),
            "invoice_value": _stringify(invoice.get("date")),
            "ledger_value":  _stringify(ledger.get("date")),
        },
        "amount": {
            "score": round(s_amt, 4),
            "weight": w["amount"],
            "contribution": round(s_amt * w["amount"], 4),
            "invoice_value": _stringify(invoice.get("amount")),
            "ledger_value":  _stringify(ledger.get("debit") or ledger.get("credit")),
        },
    }
