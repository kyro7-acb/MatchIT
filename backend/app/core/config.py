import re
import os
from pathlib import Path

# Similarity weights (must sum to 1.0)
WEIGHTS = {
    "invoice_number": 0.40,
    "vendor":         0.25,
    "date":           0.20,
    "amount":         0.15,
}

# Classification thresholds
THRESHOLDS = {
    "auto_match": 0.90,
    "review":     0.70,
}

# Date / amount tolerance
DATE_TOLERANCE_DAYS       = 3
AMOUNT_TOLERANCE_PERCENT  = 0.01

# File upload settings
MAX_FILE_SIZE_MB   = 20
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".xlsx", ".xls", ".csv"}
UPLOAD_DIR         = Path(os.getenv("UPLOAD_DIR", "/tmp/matchit_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:ayush123%40K@localhost:5432/postgres"
)

# CORS origins
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# Vendor stop-words
VENDOR_STOPWORDS = {
    "pvt", "ltd", "limited", "private", "inc", "incorporated",
    "llc", "co", "company", "corp", "corporation", "and", "the",
}

# Regex patterns
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

LOG_LEVEL = "INFO"   # DEBUG | INFO | WARNING | ERROR
