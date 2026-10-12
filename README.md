<div align="center">

# 🔗 matchIT

### Automated Invoice-to-Ledger Reconciliation

Upload your invoices and your accounting ledger. matchIT pairs every invoice with
its ledger entry. It copes with reformatted reference numbers, abbreviated vendor
names, shifted dates and rounding differences, and explains every decision it makes.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL%20%2F%20SQLite-4169E1?logo=postgresql&logoColor=white)

![matchIT landing page](docs/screenshots/landing.png)

</div>

---

## Table of contents

- [The idea](#the-idea)
- [Screenshots](#screenshots)
- [How it works](#how-it-works)
- [Algorithms](#algorithms)
- [Getting started](#getting-started)
- [Using matchIT](#using-matchit)
- [Supported file layouts](#supported-file-layouts)
- [API reference](#api-reference)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Contributors](#contributors)

---

## The idea

Reconciliation means checking that every supplier invoice was recorded in the books.
It is slow, repetitive work, and it is hard to automate with a plain lookup because
the two sides almost never agree character for character:

| On the invoice              | In the ledger                          | Why a simple lookup fails                        |
|-----------------------------|----------------------------------------|--------------------------------------------------|
| `INV-0759`                  | `INV0759`                              | Separators dropped during data entry             |
| `Kathmandu Supplies Co.`    | `KTM SUPPLIES COMPANY`                 | Abbreviations, casing, legal suffixes            |
| `05/02/2026`                | `2026-02-06`                           | Different formats, and booked a day later        |
| `7,800.00`                  | `7,750.00`                             | Rounding, discounts, small adjustments           |
| `0761` on the invoice       | `PI/RM-L/82-83/0116` (voucher number)  | The real reference is buried in the narration    |

matchIT handles this in three stages:

1. **Extract**: read messy Excel/CSV exports with **pandas**, including real ERP
   printouts with report titles, buried header rows, vendor sub-headings and
   subtotal lines.
2. **Score**: compare every invoice against every ledger entry on four fields
   (invoice number, vendor, date, amount), using a similarity measure suited to
   each field.
3. **Assign**: run the **Hungarian algorithm** to find the best one-to-one pairing
   across the whole batch, then sort each pair into **Auto match**, **Review** or
   **Unmatched**.

Every score breaks down field by field, and a person can override any decision
with a note. **No machine learning is used.** The engine is deterministic and
rule-based, and every result can be explained.

---

## Screenshots

**1. Upload invoices, then the ledger.** Both drop zones accept `.xlsx`, `.xls` and `.csv`.

![Upload step](docs/screenshots/upload.png)

**2. Results.** A summary, filters by status, and one card per invoice ↔ ledger pair.

![Results page](docs/screenshots/results.png)

**3. Explainable scores.** Expand any card to see which fields matched, how closely,
and how much each one added to the final score.

![Score breakdown](docs/screenshots/breakdown.png)

**4. Human override.** Confirm, reject or keep a pair under review, with an optional note.

![Override dialog](docs/screenshots/override.png)

After the override, the pair is shown as **Confirmed**, and the summary and filters update:

![After override](docs/screenshots/after-override.png)

---

## How it works

```
 invoices.xlsx / .csv                 ledger.xlsx / .csv
         │                                    │
         ▼                                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. EXTRACT        extract.py  (pandas)                       │
│    find the header row · map columns by keyword · detect     │
│    single-invoice forms · track vendor context lines ·       │
│    skip subtotal / balance rows · pull invoice refs out of   │
│    narration text                                            │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. NORMALISE      preprocess.py                              │
│    "INV-0759" → "INV0759"      "Kathmandu Supplies Co." →    │
│    "0761" → "761"               "kathmandu supplies"         │
│    "05/02/2026" → datetime      "Rs. 12,500.50" → 12500.5    │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. FILTER         optimizer.filter_candidates                │
│    drop ledger rows > 60 days from every invoice date        │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. SCORE          similarity.py  → n × m score matrix        │
│    0.40·Levenshtein(inv no) + 0.25·Jaro-Winkler(vendor)      │
│  + 0.20·date proximity       + 0.15·amount proximity         │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. ASSIGN         optimizer.py  (Hungarian algorithm)        │
│    globally optimal one-to-one invoice ↔ ledger pairing      │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. CLASSIFY       classifier.py                              │
│    ≥ 0.90 auto_match · ≥ 0.70 review · otherwise unmatched   │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
   stored in the database → React UI / CSV / JSON export
```

---

## Algorithms

All four similarity measures are **implemented from scratch** in
`backend/app/services/similarity.py`. The only library algorithm is SciPy's Hungarian solver.

### 1. Levenshtein similarity (invoice number ↔ reference, weight 40%)

The Levenshtein distance is the minimum number of single-character insertions,
deletions or substitutions needed to turn one string into the other. It is computed
with the classic dynamic-programming table:

```
dp[i][j] = dp[i-1][j-1]                                   if a[i] == b[j]
         = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])  otherwise
```

It becomes a similarity in `[0, 1]`:

```
sim(a, b) = 1 − distance(a, b) / max(|a|, |b|)
```

References are **normalised first**: upper-cased, separators and symbols removed,
and leading zeros stripped from purely numeric references. So `INV-0759` and
`INV0759` score **1.0**. A transposition such as `INV0762` vs `INV0726` costs two
edits, so it scores `1 − 2/7 = 0.714`. That pair lands in *Review* instead of
being silently accepted or rejected.

### 2. Jaro-Winkler similarity (vendor name, weight 25%)

Vendor names differ in ways edit distance handles badly (`KTM` vs `Kathmandu`, word
order, suffixes). Jaro-Winkler suits short names because it rewards characters that
appear in roughly the same position, and gives extra weight to a shared prefix.

```
Jaro  = ⅓ · ( m/|a| + m/|b| + (m − t/2)/m )
        m = matching characters (within a window of max(|a|,|b|)/2 − 1)
        t = transpositions among the matched characters

Jaro-Winkler = Jaro + ℓ · p · (1 − Jaro)
        ℓ = length of the common prefix (max 4),  p = 0.1
```

Before comparing, vendor names are lower-cased, stripped of punctuation, and
cleared of legal stop-words (`pvt`, `ltd`, `co`, `company`, `inc`, …). So
`ANNAPURNA PAPER MILLS PVT. LTD.` and `Annapurna Paper Mills` are identical.

### 3. Date proximity (weight 20%)

Invoices are often booked a few days after they are issued. The date score decays
linearly within a tolerance window (default **3 days**):

```
Δ = |invoice_date − ledger_date| in days

score = 1.0                    if Δ = 0
      = 1 − Δ / (2 · 3)        if Δ ≤ 3      → 1 day: 0.83, 3 days: 0.50
      = 0.0                    otherwise
```

Dates are parsed from more than 20 formats (day-first wins on ambiguous input).
Real Excel date cells are handled too. Dates more than a year in the future are
treated as unparseable, because they are almost always **Bikram Sambat** (Nepali
calendar) dates such as `2082-10-19` that would otherwise be compared as if they
were Gregorian.

### 4. Amount proximity (weight 15%)

```
ε = |a − b| / max(|a|, |b|)          (relative error)

score = 1.0               if ε ≤ 1 %
      = e^(−10·ε)         otherwise   → 5 % off: 0.61, 20 % off: 0.14
```

Currency prefixes (`Rs.`, `NPR`, `$`…) and both Western and South-Asian thousands
separators (`1,13,000.00`) are handled. On the ledger side, the debit amount is used
when present, and the credit amount otherwise.

### 5. Weighted score

```
score = 0.40·S_invoice_no + 0.25·S_vendor + 0.20·S_date + 0.15·S_amount
```

Worked example from the screenshots (`INV-0762` ↔ `INV-0726`):

| Field          | Invoice                 | Ledger                            | Score  | × Weight | Contribution |
|----------------|-------------------------|-----------------------------------|--------|----------|--------------|
| Invoice number | `INV-0762`              | `INV-0726`                        | 0.7143 | 0.40     | 0.2857       |
| Vendor         | `Annapurna Paper Mills` | `ANNAPURNA PAPER MILLS PVT. LTD.` | 1.0000 | 0.25     | 0.2500       |
| Date           | `12/02/2026`            | `2026-02-15` (3 days later)       | 0.5000 | 0.20     | 0.1000       |
| Amount         | `18,450.00`             | `18,450.00`                       | 1.0000 | 0.15     | 0.1500       |
| **Total**      |                         |                                   |        |          | **0.7857 → Review** |

### 6. Hungarian algorithm (global assignment)

Matching each invoice to its single highest-scoring ledger row (greedy matching) can
assign two invoices to the same entry, or take a ledger row that another invoice
needed more. matchIT treats pairing as an **assignment problem**: choose a
one-to-one pairing that maximises the **sum** of all scores.

The score matrix `S` (n invoices × m ledger rows) becomes a cost matrix `C = 1 − S`.
That goes to `scipy.optimize.linear_sum_assignment`, a Hungarian-style solver that
finds the minimum-cost assignment in polynomial time (about `O(n³)`). It also
works for non-square matrices:

- **More ledger rows than invoices** (the usual case): the extra rows stay unpaired.
- **More invoices than ledger rows**: the invoices that can't be paired are
  reported in the *Skipped* section instead of being dropped silently.

### 7. Candidate filtering and classification

Before scoring, ledger rows dated more than **60 days** from *every* invoice are
removed. This shrinks the matrix and keeps old entries from being paired with new
invoices. Each removed row is listed under *Skipped* with its reason.

After assignment, each pair is classified:

| Score         | Status         | Meaning                                    |
|---------------|----------------|--------------------------------------------|
| `≥ 0.90`      | **Auto match** | Safe to accept without review              |
| `0.70 – 0.89` | **Review**     | Probably correct; a person should check it |
| `< 0.70`      | **Unmatched**  | No convincing ledger counterpart           |

Any pair can then be **Confirmed**, **Rejected** or kept under **Review** by a person.
Overrides are stored with a note and a timestamp.

---

## Getting started

### Prerequisites

| Tool                         | Version | Check with         |
|------------------------------|---------|--------------------|
| Python                       | 3.10+   | `python --version` |
| Node.js                      | 18+     | `node --version`   |
| PostgreSQL *(optional)*      | 13+     | `psql --version`   |

> matchIT uses **SQLite by default**, so you can run it without installing a
> database. Switch to PostgreSQL with one environment variable (see step 3).

### 1. Clone the repository

```bash
git clone https://github.com/kyro7-acb/matchit.git
cd matchit
```

### 2. Set up the backend

```bash
cd backend

# create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements.txt
```

### 3. Configure the database *(optional)*

Copy the example settings file:

```bash
cp .env.example .env              # Windows: copy .env.example .env
```

With no changes, matchIT uses SQLite and creates `backend/matchit.db` on first run.
To use **PostgreSQL** instead, create a database and point `DATABASE_URL` at it in `backend/.env`:

```bash
createdb matchit                  # or: CREATE DATABASE matchit;  in psql
```

```ini
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/matchit
```

The tables are created automatically when the server starts. No migrations are needed.

### 4. Start the API server

```bash
# still inside backend/ with the venv active
uvicorn app.main:app --reload --port 8000
```

Check that it is running:

- Health check: <http://localhost:8000/health> should return `{"status": "ok", ...}`
- Interactive API docs (Swagger): <http://localhost:8000/docs>

### 5. Set up and start the frontend

Open a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, then click **Open app** or **Try matchIT now**.

> The frontend calls the API at `http://localhost:8000/api` by default.
> If your backend runs somewhere else, create `frontend/.env.local` with
> `VITE_API_URL=http://your-host:8000/api`, and add your frontend's address to
> `CORS_ORIGINS` in `backend/.env`.

### 6. Try it with the sample data

The [`sample_data/`](sample_data) folder contains realistic demo files:

| File                | What it shows                                                                                                  |
|---------------------|----------------------------------------------------------------------------------------------------------------|
| `invoices.xlsx`     | An invoice register (7 invoices) with a report title above the header and a *Grand Total* footer row           |
| `Invoice_0761.xlsx` | One printed tax invoice laid out as a form (label/value cells, line items, VAT, Grand Total)                   |
| `ledger.xlsx`       | An ERP subledger export: metadata rows, vendor context lines (`S712 [ID : …]`), Bikram Sambat dates, opening/closing balance rows, invoice numbers hidden in narration text |

1. **Invoices step**: drop `invoices.xlsx` **and** `Invoice_0761.xlsx`, then click **Upload invoices →**.
2. **Ledger step**: drop `ledger.xlsx`, then click **Upload ledger →**.
3. **Match step**: click **Run matching pipeline**.

Expected result: **5 auto matches, 2 for review, 1 unmatched, 1 skipped**, as in the screenshots.

To regenerate or modify the sample files:

```bash
python sample_data/make_samples.py      # needs openpyxl (installed with the backend)
```

---

## Using matchIT

| Step               | What happens                                                                                                                                                                                                                                       |
|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **1. Invoices**    | Upload one or more invoice files. A new session is created, and the number of extracted invoices is shown. If nothing can be extracted, you'll see an error explaining why.                                                                       |
| **2. Ledger**      | Upload the ledger export(s) for the same period.                                                                                                                                                                                                   |
| **3. Match**       | Runs the pipeline. It usually takes well under a second.                                                                                                                                                                                           |
| **4. Results**     | Filter by status, expand a card to compare both sides, open **Show score breakdown** for the per-field explanation, and use **Override decision** to confirm or reject a pair. Download everything as **CSV** or **JSON** with the buttons in the summary. |
| **New session**    | Clears everything and starts over. Past sessions stay in the database and can be listed with `GET /api/sessions`.                                                                                                                                  |

---

## Supported file layouts

Extraction uses **pandas** (`openpyxl` for `.xlsx`, `xlrd` for legacy `.xls`).
Every sheet in a workbook is read. Files are checked on upload for extension,
size (20 MB max) and content (magic bytes), so a renamed image is rejected.

**Ledger files**

- The header row is found automatically. It doesn't have to be the first row: matchIT
  picks the row (among the first 30) whose cells match the most known column types.
- Columns are mapped by keyword, using the most specific match, so
  `DOC No.`, `Ref`, `Voucher` → reference; `Debit Amount`, `Dr` → debit;
  `Party`, `Supplier` → vendor; `Narration`, `Particulars` → narration.
  Short abbreviations (`dr`, `cr`, `ref`) must stand alone, so `Description`
  is never read as a credit column.
- **Vendor context lines** such as `S712 [ID : BHAGWATI STEEL INDUSTRIES LTD.]`
  set the vendor for every row below them.
- **Invoice references are pulled out of narration** (`Ref. Doc No. 0761`,
  `Inv No. GL5521`, `Bill No 1043`, `Invoice No. EG/2026/118`). They are preferred
  over the internal ERP voucher number, which never appears on a supplier's invoice.
- Opening balance, operation total, closing balance, "Printed on…" and note rows are skipped.

**Invoice files**, in either of two shapes, detected automatically:

- **Register**: one row per invoice under a header such as
  `Invoice No. | Vendor | Invoice Date | Amount`. Total/subtotal rows are ignored.
- **Single invoice form**: a printed layout where labels and values sit in
  neighbouring cells (`Invoice No.: | 0761`). The vendor is taken from the
  letterhead line, and the amount from **Grand Total** (after VAT), not from
  the line items or the taxable amount. A `Miti` (Bikram Sambat) date label is ignored.

---

## API reference

Base URL: `http://localhost:8000`. Interactive documentation is at `/docs`.

| Method | Endpoint                                     | Description                                                       |
|--------|----------------------------------------------|-------------------------------------------------------------------|
| `GET`  | `/health`                                    | Health check                                                      |
| `POST` | `/api/upload-invoice`                        | Multipart `files[]`. Creates a session and returns extracted invoices |
| `POST` | `/api/upload-ledger?session_id=…`            | Multipart `files[]`. Adds ledger entries to the session           |
| `POST` | `/api/match?session_id=…`                    | Runs the pipeline (or returns the cached result)                  |
| `GET`  | `/api/match/{session_id}`                    | Gets a previously computed result                                 |
| `POST` | `/api/match/{match_id}/override`             | Body `{"status": "confirmed" \| "rejected" \| "review" \| …, "note": "…"}` |
| `GET`  | `/api/match/{session_id}/export?fmt=csv`     | Downloads results as `csv` or `json`                              |
| `GET`  | `/api/sessions?limit=20&offset=0`            | Lists past sessions with summaries                                |

Example with `curl`:

```bash
SID=$(curl -s -F files=@sample_data/invoices.xlsx -F files=@sample_data/Invoice_0761.xlsx \
      http://localhost:8000/api/upload-invoice | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
curl -s -F files=@sample_data/ledger.xlsx "http://localhost:8000/api/upload-ledger?session_id=$SID"
curl -s -X POST "http://localhost:8000/api/match?session_id=$SID"
```

---

## Configuration

**Environment variables** (`backend/.env`, see `.env.example`):

| Variable       | Default                                      | Description                                  |
|----------------|----------------------------------------------|----------------------------------------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./matchit.db`           | SQLAlchemy async URL (SQLite or PostgreSQL)  |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000`| Allowed frontend origins (comma-separated)   |
| `UPLOAD_DIR`   | `<system temp>/matchit_uploads`              | Where uploaded files are stored              |
| `LOG_LEVEL`    | `INFO`                                       | `DEBUG` shows every pairwise score           |

**Matching parameters** (`backend/app/core/config.py`):

| Parameter                     | Default | Description                                         |
|-------------------------------|---------|-----------------------------------------------------|
| `WEIGHTS["invoice_number"]`   | `0.40`  | Weight of the invoice-number similarity             |
| `WEIGHTS["vendor"]`           | `0.25`  | Weight of the vendor-name similarity                |
| `WEIGHTS["date"]`             | `0.20`  | Weight of the date proximity                        |
| `WEIGHTS["amount"]`           | `0.15`  | Weight of the amount proximity                      |
| `THRESHOLDS["auto_match"]`    | `0.90`  | Score at or above which a pair is auto-matched      |
| `THRESHOLDS["review"]`        | `0.70`  | Score at or above which a pair goes to review       |
| `DATE_TOLERANCE_DAYS`         | `3`     | Date difference that still earns partial credit     |
| `AMOUNT_TOLERANCE_PERCENT`    | `0.01`  | Relative amount error that still counts as exact    |
| `CANDIDATE_WINDOW_DAYS`       | `60`    | Ledger rows further than this from all invoices are skipped |
| `MAX_FILE_SIZE_MB`            | `20`    | Upload size limit per file                          |

The weights must add up to `1.0`. The explanation panel in the UI reads the
weights from the API, so changing them here is enough.

---

## Project structure

```
matchit/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, startup (creates tables)
│   │   ├── api/
│   │   │   ├── upload.py            # POST /upload-invoice, /upload-ledger
│   │   │   └── match.py             # match, results, override, export, sessions
│   │   ├── services/
│   │   │   ├── extract.py           # pandas extraction (registers, forms, ERP ledgers)
│   │   │   ├── preprocess.py        # normalisation of references, vendors, dates, amounts
│   │   │   ├── similarity.py        # Levenshtein, Jaro-Winkler, date & amount scores
│   │   │   ├── optimizer.py         # candidate filter + Hungarian assignment
│   │   │   ├── classifier.py        # score → auto_match / review / unmatched
│   │   │   └── matching_service.py  # orchestrates the pipeline + persistence
│   │   ├── core/
│   │   │   ├── config.py            # weights, thresholds, env settings
│   │   │   └── utils.py             # logging, date & amount parsing
│   │   ├── db/                      # SQLAlchemy models + async session
│   │   ├── models/schemas.py        # Pydantic request/response models
│   │   └── utils/file_validator.py  # extension, size and magic-byte checks
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/                   # LandingPage, MatchPage
│       ├── components/
│       │   ├── upload/DropZone.jsx
│       │   └── results/             # SummaryBar, MatchCard, ExplainPanel, OverrideModal, …
│       ├── hooks/useMatching.js     # upload → match state machine
│       └── utils/api.js             # API client
├── sample_data/                     # demo invoices + ledger, and the script that builds them
└── docs/screenshots/
```

**Tech stack:** FastAPI · SQLAlchemy 2 (async) · pandas · NumPy · SciPy ·
React 19 · React Router · Vite · Tailwind CSS · PostgreSQL / SQLite

---

## Contributors

matchIT was built by:

| | Contributor | GitHub |
|---|---|---|
| <img src="https://github.com/kyro7-acb.png" width="48" height="48" alt="Ayush" /> | **Ayush** | [@kyro7-acb](https://github.com/kyro7-acb) |
| <img src="https://github.com/riteshkhadka69-stack.png" width="48" height="48" alt="Ritesh" /> | **Ritesh** | [@riteshkhadka69-stack](https://github.com/riteshkhadka69-stack) |
| <img src="https://github.com/barshaha.png" width="48" height="48" alt="Barsha" /> | **Barsha** | [@barshaha](https://github.com/barshaha) |

Trinity International College · TU BSc.CSIT
