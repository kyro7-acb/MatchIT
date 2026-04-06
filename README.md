# Invoice-to-Ledger Matching Engine

Automated reconciliation of scanned invoice images against ledger entries using:
- **PaddleOCR** for text extraction
- **Rule-based field detection** (regex + layout hints)
- **Weighted multi-field similarity** (Levenshtein, Jaro-Winkler, date & amount metrics)
- **Hungarian algorithm** for globally optimal one-to-one matching
- **Threshold classification** → `auto_match` / `review` / `unmatched`

---

## Project Structure

```
invoice_matcher/
├── services/
│   ├── __init__.py
│   ├── extract.py       # OCR + rule-based field extraction
│   ├── preprocess.py    # Deterministic normalization
│   ├── similarity.py    # Weighted similarity scoring
│   ├── optimizer.py     # Hungarian algorithm matching
│   └── classifier.py    # Score → status label
├── main.py              # Pipeline runner (CLI entry point)
├── config.py            # Weights, thresholds, regex patterns
├── utils.py             # Shared helpers (logging, date/amount parsing)
├── requirements.txt
└── test_data/
    ├── mock_invoices.json
    └── mock_ledger.json
```

---

## Installation

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate          
Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **GPU users:** Replace `paddlepaddle` in `requirements.txt` with `paddlepaddle-gpu`
> and ensure CUDA is installed before running pip install.

---

## Running the Pipeline

### Option A — Mock mode (no images required, great for first run)

```bash
python main.py --mock
```

### Option B — Real invoice images

```bash
python main.py \
  --image path/to/invoice1.jpg path/to/invoice2.jpg \
  --ledger test_data/mock_ledger.json
```

### Option C — Save JSON output

```bash
python main.py --mock --output results.json
```

### Verbose logging

```bash
python main.py --mock --log-level DEBUG
```

---

## Configuration

All tunable parameters live in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `WEIGHTS["invoice_number"]` | `0.40` | Weight for invoice number similarity |
| `WEIGHTS["vendor"]` | `0.25` | Weight for vendor name similarity |
| `WEIGHTS["date"]` | `0.20` | Weight for date similarity |
| `WEIGHTS["amount"]` | `0.15` | Weight for amount similarity |
| `THRESHOLDS["auto_match"]` | `0.90` | Score ≥ this → auto_match |
| `THRESHOLDS["review"]` | `0.70` | Score ≥ this → review |
| `DATE_TOLERANCE_DAYS` | `3` | Days within which date scores as 1.0 |
| `AMOUNT_TOLERANCE_PERCENT` | `0.01` | 1% relative error → full amount score |

---

## Pipeline Explained

```
Invoice Image(s)
      │
      ▼
extract.py          PaddleOCR → text blocks → regex/keyword field detection
      │               → invoice_number, vendor_name, date, amount
      ▼
preprocess.py       Normalize: lowercase, strip specials, parse dates/amounts
      │
      ▼
Candidate Filter    Drop ledger entries outside ±60-day window (optional)
      │
      ▼
similarity.py       Build n×m score matrix
      │               invoice_number: Levenshtein ratio
      │               vendor:         Jaro-Winkler
      │               date:           tolerance-window decay
      │               amount:         relative-error decay
      ▼
optimizer.py        Hungarian algorithm (scipy.optimize.linear_sum_assignment)
      │               → globally optimal one-to-one assignment
      ▼
classifier.py       score ≥ 0.90 → auto_match
      │             score ≥ 0.70 → review
      │             else         → unmatched
      ▼
JSON + Console Table
```

---

## Ledger JSON Format

```json
[
  {
    "reference": "INV-2024-001",
    "vendor":    "Himalayan Traders Pvt Ltd",
    "date":      "15/01/2024",
    "debit":     "45000.00",
    "credit":    null
  }
]
```

---

## Extending the System

### Improve OCR accuracy
- Pre-process images: deskew, denoise, increase contrast (use OpenCV before passing to PaddleOCR)
- Use `paddleocr` with `use_angle_cls=True` for rotated documents
- Fine-tune PaddleOCR on domain-specific invoice fonts using [PaddleOCR's training docs](https://paddlepaddle.github.io/PaddleOCR/latest/en/ppocr/model_train/recognition.html)

### Add new similarity fields
1. Add the new weight key to `WEIGHTS` in `config.py`
2. Implement a `field_similarity(a, b)` function in `similarity.py`
3. Include it in `compute_similarity()` weighted sum

### Add a database layer
- Replace JSON file I/O in `main.py` with SQLAlchemy or psycopg2 calls
- Store classified results in a `matches` table with `status`, `score`, and foreign keys to invoices/ledger

### Build a dashboard
- Expose `run_pipeline_from_mock()` / `run_pipeline_from_images()` via a FastAPI endpoint
- Feed results to a React/Streamlit frontend for human review of `review` matches

---

## Notes & Assumptions

- **No ML is used** — matching is entirely rule-based + algorithm-based, as specified.
- Levenshtein, Jaro-Winkler, date similarity, and amount similarity are **implemented from scratch** (no external string-similarity library dependency).
- PaddleOCR is only imported when `--image` mode is used; `--mock` mode has zero OCR dependency.
- The Hungarian algorithm correctly handles **non-square matrices** (more invoices than ledger entries or vice versa).
- When `debit_amount` is null, `credit_amount` is used as the comparison amount for ledger entries.
