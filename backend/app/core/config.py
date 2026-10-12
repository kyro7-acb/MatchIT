import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

# Load settings from backend/.env (if present) before reading env vars below.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

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

# Candidate filtering: ledger entries further than this from every invoice
# date are dropped before scoring.
CANDIDATE_WINDOW_DAYS = 60

# File upload settings
MAX_FILE_SIZE_MB   = 20
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
UPLOAD_DIR         = Path(os.getenv("UPLOAD_DIR", Path(tempfile.gettempdir()) / "matchit_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Database — PostgreSQL in production, SQLite works out of the box for local use.
#   PostgreSQL: postgresql+asyncpg://user:password@localhost:5432/matchit
#   SQLite:     sqlite+aiosqlite:///./matchit.db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./matchit.db")

# CORS origins
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# Vendor stop-words
VENDOR_STOPWORDS = {
    "pvt", "ltd", "limited", "private", "inc", "incorporated",
    "llc", "co", "company", "corp", "corporation", "and", "the",
}

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")   # DEBUG | INFO | WARNING | ERROR
