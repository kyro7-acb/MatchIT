"""
config.py
---------
Central configuration for the Invoice-to-Ledger Matching Engine.
Tune weights, thresholds, and regex patterns here without touching business logic.
"""

import re

# ---------------------------------------------------------------------------
# Similarity weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "invoice_number": 0.40,   # w1 — highest weight; invoice numbers are most discriminative
    "vendor":         0.25,   # w2
    "date":           0.20,   # w3
    "amount":         0.15,   # w4
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# ---------------------------------------------------------------------------
# Classification thresholds
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "auto_match": 0.90,   # score >= 0.90  → auto_match
    "review":     0.70,   # score >= 0.70  → review
    # below review  → unmatched
}

# ---------------------------------------------------------------------------
# Date similarity tolerance (in days)
# ---------------------------------------------------------------------------
DATE_TOLERANCE_DAYS = 3   # within 3 days → full date score

# ---------------------------------------------------------------------------
# Amount similarity tolerance
# ---------------------------------------------------------------------------
AMOUNT_TOLERANCE_PERCENT = 0.01   # 1% tolerance → full amount score

# ---------------------------------------------------------------------------
# Regex patterns for field extraction
# ---------------------------------------------------------------------------
PATTERNS = {
    "invoice_number": re.compile(
        r"(?:invoice\s*(?:no|num|number|#)|inv\.?\s*(?:no|#)?)\s*[:\-]?\s*([A-Z0-9][\w\-/]{2,20})",
        re.IGNORECASE,
    ),
    "date": re.compile(
        r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}"
        r"|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}"
        r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}"
        r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
        re.IGNORECASE,
    ),
    "amount": re.compile(
        r"(?:total|amount|amt|grand\s*total|net\s*amount|payable)\s*[:\-]?\s*"
        r"(?:USD|EUR|GBP|NPR|Rs\.?|INR|\$|\u20ac|\xa3)?\s*([\d,]+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    ),
    "currency_amount": re.compile(
        r"(?:USD|EUR|GBP|NPR|Rs\.?|INR|\$|\u20ac|\xa3)\s*([\d,]+(?:\.\d{1,2})?)"
        r"|([\d,]+(?:\.\d{1,2})?)\s*(?:USD|EUR|GBP|NPR|Rs\.?|INR)",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Vendor name keywords to strip during normalization
# ---------------------------------------------------------------------------
VENDOR_STOPWORDS = {
    "pvt", "ltd", "limited", "private", "inc", "incorporated",
    "llc", "co", "company", "corp", "corporation", "and", "the",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"   # DEBUG | INFO | WARNING | ERROR
