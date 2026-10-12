"""
backend/app/services/extract.py
--------------------------------
Extract structured invoice and ledger records from Excel (.xlsx / .xls) and
CSV files using pandas.

Every sheet is read raw (header=None) and then interpreted by rule-based
logic, because real accounting exports rarely start with a clean header row:

  • Ledger files     → buried-header detection + keyword column mapping +
                       vendor-context tracking  (extract_ledger_from_dataframe)
  • Invoice files    → either a single printed invoice "form" (label/value
                       cells) or a tabular invoice register, detected
                       automatically          (extract_invoices_from_dataframe)
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.core.utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _read_sheets(file_path: str) -> dict[str, pd.DataFrame]:
    """Read every sheet of an Excel workbook (or a CSV) without assuming a header row."""
    suffix = Path(file_path).suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(file_path, sheet_name=None, header=None, dtype=object)
    if suffix == ".csv":
        return {"csv": pd.read_csv(file_path, header=None, dtype=object)}
    raise ValueError(f"Unsupported file format: {suffix}")


def _cell_str(cell: Any) -> str:
    """
    Safely stringify a raw pandas cell.

    - NaN / NaT / None          → ""
    - real date/datetime cells  → ISO "YYYY-MM-DD" (so the date parser can read them)
    - whole-number floats       → "761" instead of "761.0" (Excel stores numeric
                                  invoice numbers as floats; the trailing ".0"
                                  would otherwise corrupt the reference)
    """
    if cell is None:
        return ""
    try:
        if pd.isna(cell):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(cell, (datetime, date)):
        return cell.strftime("%Y-%m-%d")
    if isinstance(cell, float) and cell.is_integer():
        return str(int(cell))
    return str(cell).strip()


def _contains_keyword(text: str, keyword: str) -> bool:
    """
    True if `keyword` appears in the (lower-cased) header `text`.

    Longer keywords are matched as substrings so run-together headers such
    as "InvoiceNo" or "VendorName" still resolve. Short abbreviations
    (≤ 3 chars: "dr", "cr", "ref", "amt") must stand alone, otherwise "cr"
    would match "desCRiption", "dr" would match "adDRess", and so on.
    """
    kw = keyword.strip()
    if not kw:
        return False
    if len(kw) > 3:
        return kw in text
    return re.search(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", text) is not None


def _best_keyword_field(header: str, keyword_groups: dict[str, list[str]]) -> Optional[str]:
    """
    Map a normalised header cell to the field whose matching keyword is the
    most specific (longest). This way "Invoice Date" resolves to `date` via
    "invoice date" rather than to `invoice_number` via the bare "invoice",
    and "Debit Amount" resolves to `debit` rather than the generic `amount`.
    """
    best_field: Optional[str] = None
    best_len = 0
    for field, keywords in keyword_groups.items():
        for kw in keywords:
            if len(kw.strip()) > best_len and _contains_keyword(header, kw):
                best_field, best_len = field, len(kw.strip())
    return best_field


# ---------------------------------------------------------------------------
# Ledger extraction
# ---------------------------------------------------------------------------
#
# Real-world accounting exports (e.g. Nepali ERP "subledger detail" printouts)
# are NOT clean tables:
#   - The real header row is buried several rows down, under company name /
#     fiscal-year / address / report-title metadata lines.
#   - Column headers rarely match a fixed alias list exactly
#     ("DOC No." vs "invoice_no", "GL - Ledger / SubLedger / Narration" vs
#     "vendor"), so exact-equality alias matching silently maps nothing.
#   - The vendor/party name often isn't a column at all — it appears once in
#     a standalone "subledger id" line (e.g. "S712 [ID : ACME LTD.]") that
#     applies to every transaction row underneath it, until the next such
#     line appears.
#   - Reference/voucher numbers can have an annotation glued on with a
#     newline, e.g. "PI/RM-L/82-83/0110\n(Post Journal)".
#   - Opening-balance / subtotal / closing-balance / "Printed on ..." /
#     footnote rows have no reference and should not be treated as
#     transactions.
#
# The functions below handle all of this generically (not hardcoded to any
# one vendor or template) so the same code works for clean tables *and*
# messy ERP printouts.

# Column keyword groups, used for BOTH header detection and column
# classification. Matching is keyword-based (not exact equality, see
# `_contains_keyword`) so "Debit Amount", "debit amt", "DR" etc. all
# resolve to "debit".
_LEDGER_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "reference": ["reference", "ref", "invoice no", "invoice_no", "voucher", "doc no", "docno", "doc.no"],
    "vendor":    ["vendor", "supplier", "party", "vendor name"],
    "date":      ["doc date", "invoice date", "txn date", "transaction date", "date"],
    # Ledgers frequently have BOTH a Gregorian "date" column and a
    # secondary local-calendar date column (e.g. "Miti" in Nepali BS
    # calendar). We deliberately do NOT match "miti" as a date alias so the
    # Gregorian column always wins.
    "debit":     ["debit amount", "debit amt", "debit", " dr"],
    "credit":    ["credit amount", "credit amt", "credit", " cr"],
    "amount":    ["amount", "amt", "total"],
    # A "narration" style column ("GL - Ledger / SubLedger / Narration",
    # "Particulars", "Description"...) is text, not a vendor name — it's
    # only used as a fallback source for the vendor when no explicit
    # vendor column and no subledger context line exist.
    "narration": ["narration", "description", "particulars", "details", "ledger", "subledger"],
}

# Rows that are report furniture, not transactions, even if they contain
# numbers in the debit/credit columns.
_NON_TRANSACTION_ROW_RE = re.compile(
    r"operation total|closing balance|opening b/?l|subledger opening|"
    r"printed on|note\s*:|account summary|sl\s*-\s*account",
    re.IGNORECASE,
)

# A standalone "subledger id" context line, e.g.
# "S712  [ID : BHAGWATI STEEL INDUSTRIES LTD.]"
_SUBLEDGER_CONTEXT_RE = re.compile(r"\[\s*ID\s*:\s*(.+?)\s*\]", re.IGNORECASE)


def _normalize_header_cell(cell: Any) -> str:
    return re.sub(r"\s+", " ", _cell_str(cell)).lower()


def _classify_ledger_header_cell(cell: Any) -> Optional[str]:
    """Map a single raw header cell to a semantic field name, or None."""
    h = _normalize_header_cell(cell)
    if not h:
        return None
    keyword_groups = _LEDGER_COLUMN_KEYWORDS
    # Running-total / carry-forward columns ("Opening Amount",
    # "Balance Amount") are not per-transaction debit/credit figures —
    # skip them so they don't get swept up by the generic "amount"
    # keyword and mistakenly used as a debit/credit fallback.
    if "opening" in h or "balance" in h:
        keyword_groups = {f: kws for f, kws in keyword_groups.items() if f != "amount"}
    return _best_keyword_field(h, keyword_groups)


def _find_ledger_header_row(raw_rows: list[list[Any]], max_scan: int = 30) -> Optional[int]:
    """
    Scan the first `max_scan` rows of a raw (header=None) sheet and return
    the index of the row that looks most like the real column header —
    i.e. the row with the most cells that classify to a distinct known
    ledger field. Requires at least 2 distinct fields to avoid false
    positives on narration text that happens to contain a keyword.
    """
    best_idx: Optional[int] = None
    best_score = 0

    for i, row in enumerate(raw_rows[:max_scan]):
        fields_found = set()
        for cell in row:
            field = _classify_ledger_header_cell(cell)
            if field:
                fields_found.add(field)
        score = len(fields_found)
        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx if best_score >= 2 else None


def _clean_reference(value: Optional[str]) -> Optional[str]:
    """Strip trailing annotations like '\\n(Post Journal)' from a doc/ref no."""
    if value is None:
        return None
    first_line = str(value).split("\n")[0].strip()
    return first_line or None


def _extract_vendor_context(row_values: list[Any]) -> Optional[str]:
    """
    Detect a standalone subledger/vendor context line such as
    "S712  [ID : BHAGWATI STEEL INDUSTRIES LTD.]" and return the vendor
    name, or None if this row isn't a context line.
    """
    non_empty = [_cell_str(v) for v in row_values if _cell_str(v)]
    if len(non_empty) != 1:
        return None
    m = _SUBLEDGER_CONTEXT_RE.search(non_empty[0])
    if m:
        return m.group(1).strip()
    return None


def _is_non_transaction_row(row_values: list[Any]) -> bool:
    joined = " ".join(_cell_str(v) for v in row_values if _cell_str(v))
    return bool(_NON_TRANSACTION_ROW_RE.search(joined))


def _fallback_vendor_from_narration(narration: Optional[str]) -> Optional[str]:
    """
    Many purchase narrations end with '... - Bhagwati Steels' i.e. the
    vendor name is the text after the last ' - ' segment. Used only when no
    vendor column and no subledger context line is available.
    """
    if not narration:
        return None
    parts = [p.strip() for p in narration.split(" - ") if p.strip()]
    if len(parts) >= 2:
        candidate = parts[-1]
        if 2 <= len(candidate.split()) <= 6:
            return candidate
    return None


# The "reference" / "DOC No." column in an ERP subledger export is an
# *internal accounting voucher number* (e.g. "PI/RM-L/82-83/0110"). It is
# generated by the accounting system and never appears anywhere on the
# vendor's actual invoice, so matching an invoice's invoice_number against
# it will always score near zero — no matter how good the fuzzy-matching
# or assignment algorithm is. The number that actually reconciles against
# the supplier invoice is usually embedded in the free-text narration
# ("...Being Payable Against Ref. Doc No. 0674 Dated: 01-Feb-26...", or
# "...Purchase Through Bill No 588 And 603..."). Pull that out and prefer
# it as the matching key whenever it's present.
_INVOICE_REF_IN_NARRATION_PATTERNS = [
    re.compile(r"ref\.?\s*doc\.?\s*no\.?\s*[:\-]?\s*([A-Za-z0-9/\-]+)", re.IGNORECASE),
    re.compile(r"\binvoice\s*no\.?\s*[:\-]?\s*([A-Za-z0-9/\-]+)", re.IGNORECASE),
    # Abbreviated form ("Inv No. 329", "Inv No Ti3412-Goc-82-83", "Inv.N.002913")
    # — a different data-entry convention from "Ref. Doc No." above, but just
    # as common. Deliberately checked after the full "invoice no" pattern
    # (not before) even though "inv" is a prefix of "invoice", because the
    # match position after "inv" in "Invoice" is "oice", not "n", so there's
    # no actual overlap risk — this is just keeping the more specific/common
    # spelling first for readability of the pattern list.
    re.compile(r"\binv\.?\s*n(?:o)?\.?\s*[:\-]?\s*([A-Za-z0-9/\-]+)", re.IGNORECASE),
    re.compile(r"\bbill\s*no\.?\s*[:\-]?\s*([0-9]+)", re.IGNORECASE),
]


def _extract_invoice_ref_from_narration(narration: Optional[str]) -> Optional[str]:
    if not narration:
        return None
    for pattern in _INVOICE_REF_IN_NARRATION_PATTERNS:
        m = pattern.search(narration)
        if m:
            return m.group(1).strip(" .,:;")
    return None


def _extract_ledger_rows_from_sheet(raw_rows: list[list[Any]]) -> list[dict]:
    """
    Core row-walking logic shared by every sheet: locate the header row,
    build a column map, then walk subsequent rows tracking vendor context
    and skipping non-transactional report furniture.
    """
    header_idx = _find_ledger_header_row(raw_rows)
    if header_idx is None:
        return []

    header_row = raw_rows[header_idx]
    col_map: dict[int, str] = {}
    for col_idx, cell in enumerate(header_row):
        field = _classify_ledger_header_cell(cell)
        if field:
            col_map[col_idx] = field

    entries: list[dict] = []
    current_vendor: Optional[str] = None

    for row in raw_rows[header_idx + 1:]:
        # Context line carrying the vendor/subledger name for rows below it
        vendor_ctx = _extract_vendor_context(row)
        if vendor_ctx:
            current_vendor = vendor_ctx
            continue

        if all(_cell_str(v) == "" for v in row):
            continue

        if _is_non_transaction_row(row):
            continue

        entry: dict = {"reference": None, "vendor": None, "date": None, "debit": None, "credit": None}
        internal_doc_no: Optional[str] = None
        narration_text: Optional[str] = None

        for col_idx, cell in enumerate(row):
            field = col_map.get(col_idx)
            if field is None:
                continue
            value = _cell_str(cell)
            if not value:
                continue
            if field == "reference":
                internal_doc_no = _clean_reference(value)
            elif field == "vendor":
                entry["vendor"] = value
            elif field == "date":
                # Don't overwrite an already-found (preferred) date column
                if entry["date"] is None:
                    entry["date"] = value
            elif field == "debit":
                entry["debit"] = value
            elif field == "credit":
                entry["credit"] = value
            elif field == "amount" and entry["debit"] is None:
                entry["debit"] = value
            elif field == "narration":
                narration_text = value

        # A transaction row needs at least a reference or a debit/credit
        # amount — otherwise it's just more report furniture we didn't
        # recognize by keyword.
        if not internal_doc_no and not entry["debit"] and not entry["credit"]:
            continue

        invoice_ref = _extract_invoice_ref_from_narration(narration_text)
        # "reference" is used downstream as the matching key against the
        # invoice's invoice_number — prefer the vendor-facing invoice
        # reference over the internal ERP voucher number whenever we found
        # one in the narration.
        entry["reference"] = invoice_ref or internal_doc_no
        entry["internal_doc_no"] = internal_doc_no
        entry["narration"] = narration_text

        if not entry["vendor"]:
            entry["vendor"] = current_vendor or _fallback_vendor_from_narration(narration_text)

        entries.append(entry)

    return entries


def extract_ledger_from_dataframe(file_path: str) -> list[dict]:
    """
    Load a structured Excel or CSV ledger file.

    Handles two shapes:
      1. Clean tables where row 0 is already the header (fast path via
         pandas' normal header inference).
      2. Real-world ERP/accounting exports where the header row is buried
         under metadata (company name, fiscal year, address, report
         title...), columns don't match a fixed alias list exactly, and
         vendor names live in standalone context lines rather than a
         column. Handled via `_extract_ledger_rows_from_sheet`.

    Returns a list of dicts: {reference, vendor, date, debit, credit}
    """
    path   = Path(file_path)
    sheets = _read_sheets(file_path)

    all_entries: list[dict] = []
    for sheet_name, df in sheets.items():
        raw_rows = df.values.tolist()
        entries = _extract_ledger_rows_from_sheet(raw_rows)
        if entries:
            logger.info("Extracted %d ledger rows from sheet '%s'.", len(entries), sheet_name)
        all_entries.extend(entries)

    logger.info("Loaded %d total ledger rows from %s.", len(all_entries), path.name)
    return all_entries


# ---------------------------------------------------------------------------
# Single-invoice "form" documents (one invoice per file)
# ---------------------------------------------------------------------------
#
# A generated invoice (e.g. "Invoice_0761.xlsx") is laid out as a printed
# form, not a table: labels and values sit in adjacent cells scattered
# across the sheet ("Invoice No.:" | "0761" ... "Invoice Date:" | "22/02/2026"),
# the vendor's own name only appears once as an unlabeled letterhead line at
# the very top, and the amount that matters for reconciliation is the
# "Grand Total" (post-VAT) buried near the bottom — not the line-item
# subtotal, and not the pre-VAT "Taxable Amount".
#
# Treating this the same way as a multi-row invoice register is actively
# wrong: a naive header-row scan sees "Invoice No.:" + "Invoice Date:" on
# the same row and mistakes that single label row for a table header, then
# reads every row below (which are more labels, not data) as if they were
# further invoice records.

# Ordered by priority: the first keyword that matches anywhere in the sheet
# wins, so more specific labels (e.g. "grand total") are checked before
# generic ones (e.g. "total") that could otherwise grab a line-item subtotal.
_INVOICE_FORM_FIELD_LABELS: dict[str, list[str]] = {
    "invoice_number": ["invoice no", "tax invoice no", "bill no"],
    # Ordered by specificity — different vendors label the same concept
    # differently ("Invoice Date", "Transaction Date", "Date of Issue", or
    # just bare "Date"). Bare "date" is deliberately last so a more
    # specific label is preferred whenever one exists on the document.
    "date":           ["invoice date", "bill date", "transaction date", "date of issue", "date"],
    "amount":         ["grand total", "net amount", "invoice amount", "total amount"],
}

# Labels that must never be treated as a match for the field above, even
# though they share a word (e.g. "Invoice Miti" is a Bikram Sambat date,
# not the Gregorian date we want; "Customer" is the buyer, not the vendor).
_INVOICE_FORM_LABEL_EXCLUDES: dict[str, list[str]] = {
    "date": ["miti", "print date"],
}

# Generic titles/words that show up as a lone cell near the top of an
# invoice but are NOT the vendor's letterhead name.
_INVOICE_FORM_NON_VENDOR_TITLES = {
    "tax invoice", "invoice", "original", "duplicate", "original copy",
    "customer copy", "office copy", "cash memo", "bill",
}


def _find_form_label_value(
    raw_rows: list[list[Any]],
    keywords: list[str],
    exclude: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Scan every cell in reading order for each keyword (in priority order).
    When a cell's text contains the keyword, return the first non-empty
    cell to its right in the same row as the value.
    """
    for kw in keywords:
        for row in raw_rows:
            for col_idx, cell in enumerate(row):
                text = _cell_str(cell).lower()
                if not text or kw not in text:
                    continue
                if exclude and any(ex in text for ex in exclude):
                    continue
                for val_cell in row[col_idx + 1:]:
                    val = _cell_str(val_cell)
                    if val:
                        return val
    return None


def _find_form_vendor_name(raw_rows: list[list[Any]], max_scan: int = 10) -> Optional[str]:
    """
    The vendor's own name is conventionally the unlabeled letterhead line
    at the very top of a printed invoice — a row with exactly one non-empty
    cell, no ':' (labels always have one in this format), and not a generic
    document title like "TAX INVOICE".
    """
    for row in raw_rows[:max_scan]:
        non_empty = [_cell_str(v) for v in row if _cell_str(v)]
        if len(non_empty) != 1:
            continue
        text = non_empty[0]
        if ":" in text:
            continue
        if text.strip().lower() in _INVOICE_FORM_NON_VENDOR_TITLES:
            continue
        return text.strip()
    return None


def _looks_like_tabular_invoice_register(raw_rows: list[list[Any]]) -> bool:
    """
    Distinguish a genuine multi-row invoice register from a single-invoice
    form that merely happens to have a label row with short, table-like
    words on it (e.g. "Bill No." / "Grand Total" as column headers vs. as
    one-off form labels). The real signal isn't "does a header-ish row
    exist" — a form's label row can accidentally look like one — it's
    "are there multiple rows below it that actually populate 2+ of the
    same mapped columns with real values", which only happens for repeated
    tabular data, never for a form's scattered label:value pairs.
    """
    header_idx = _find_invoice_header_row(raw_rows)
    if header_idx is None:
        return False

    col_map: dict[int, str] = {}
    for col_idx, cell in enumerate(raw_rows[header_idx]):
        field = _classify_invoice_header_cell(cell)
        if field:
            col_map[col_idx] = field

    populated_data_rows = 0
    for row in raw_rows[header_idx + 1:]:
        filled_fields = {
            col_map[col_idx]
            for col_idx, cell in enumerate(row)
            if col_idx in col_map and _cell_str(cell)
        }
        if len(filled_fields) >= 2:
            populated_data_rows += 1

    return populated_data_rows >= 2


def _extract_invoice_form_from_sheet(raw_rows: list[list[Any]]) -> Optional[dict]:
    """
    Parse a single-invoice form-style sheet. Returns None (so the caller can
    fall back to tabular-register parsing) if we can't find at least an
    invoice number and an amount — the two fields that actually matter for
    matching.
    """
    invoice_number = _find_form_label_value(raw_rows, _INVOICE_FORM_FIELD_LABELS["invoice_number"])
    date_val = _find_form_label_value(
        raw_rows, _INVOICE_FORM_FIELD_LABELS["date"], exclude=_INVOICE_FORM_LABEL_EXCLUDES.get("date"),
    )
    amount = _find_form_label_value(raw_rows, _INVOICE_FORM_FIELD_LABELS["amount"])
    vendor_name = _find_form_vendor_name(raw_rows)

    if not invoice_number and not amount:
        return None

    return {
        "invoice_number": invoice_number,
        "vendor_name":    vendor_name,
        "date":           date_val,
        "amount":         amount,
        "_source":        "excel_csv_form",
    }


_INVOICE_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "invoice_number": ["invoice no", "invoice number", "invoice_no", "inv no", "inv number",
                       "bill no", "voucher no", "doc no", "invoice"],
    "vendor_name":    ["vendor", "supplier", "party", "company", "billed by", "sold by"],
    "date":           ["invoice date", "bill date", "txn date", "transaction date", "date"],
    "amount":         ["invoice amount", "net amount", "grand total", "total amount",
                       "amount", "total", "amt"],
}

# Report furniture that can show up in an invoice register export and should
# never be treated as an invoice row, even if it has numbers in the amount
# column (e.g. a "Grand Total" footer row).
_INVOICE_NON_DATA_ROW_RE = re.compile(
    r"grand total|sub\s*total|page\s*\d+\s*of\s*\d+|printed on|note\s*:",
    re.IGNORECASE,
)


def _classify_invoice_header_cell(cell: Any) -> Optional[str]:
    h = _normalize_header_cell(cell)
    # "Invoice No.:" / "Invoice Date:" are form labels (value in the next
    # cell), not column headers — a printed invoice must never be mistaken
    # for a register just because two labels share a row.
    if not h or h.endswith(":"):
        return None
    return _best_keyword_field(h, _INVOICE_COLUMN_KEYWORDS)


def _find_invoice_header_row(raw_rows: list[list[Any]], max_scan: int = 30) -> Optional[int]:
    """Same buried-header detection strategy as the ledger path: scan the
    first few rows and pick the one with the most distinct recognized
    invoice fields, rather than assuming row 0 is always the header."""
    best_idx: Optional[int] = None
    best_score = 0
    for i, row in enumerate(raw_rows[:max_scan]):
        fields_found = {f for cell in row if (f := _classify_invoice_header_cell(cell))}
        if len(fields_found) > best_score:
            best_score = len(fields_found)
            best_idx = i
    return best_idx if best_score >= 2 else None


def extract_invoices_from_dataframe(file_path: str) -> list[dict]:
    """
    Load invoices from an Excel or CSV file. Each row = one invoice.

    Real invoice registers, like ledger exports, often bury the header row
    under a report title/company name, and use column names that won't
    exactly match a fixed alias list ("Bill No." vs "invoice_number",
    "Grand Total" vs "amount"). This scans for the header row and matches
    columns by keyword substring instead of assuming row 0 is the header
    and requiring an exact name match.
    """
    path   = Path(file_path)
    sheets = _read_sheets(file_path)

    invoices: list[dict] = []

    for sheet_name, df in sheets.items():
        raw_rows = df.values.tolist()

        # Try the single-invoice "form" shape first (one invoice per file,
        # labels/values scattered across the sheet) — this is the common
        # case for generated invoice documents. Skip straight to tabular
        # parsing if this sheet actually has repeated rows of real data,
        # since a form's label row can superficially resemble a table
        # header (e.g. "Bill No." as a one-off label vs. a column name).
        if not _looks_like_tabular_invoice_register(raw_rows):
            form_invoice = _extract_invoice_form_from_sheet(raw_rows)
            if form_invoice is not None:
                invoices.append(form_invoice)
                logger.info("Extracted 1 invoice from sheet '%s' via form parsing.", sheet_name)
                continue

        # Fall back to a tabular invoice register (one row per invoice).
        header_idx = _find_invoice_header_row(raw_rows)
        if header_idx is None:
            continue

        col_map: dict[int, str] = {}
        for col_idx, cell in enumerate(raw_rows[header_idx]):
            field = _classify_invoice_header_cell(cell)
            if field:
                col_map[col_idx] = field

        sheet_count = 0
        for row in raw_rows[header_idx + 1:]:
            if all(_cell_str(v) == "" for v in row):
                continue
            joined = " ".join(_cell_str(v) for v in row if _cell_str(v))
            if _INVOICE_NON_DATA_ROW_RE.search(joined):
                continue

            inv: dict = {"invoice_number": None, "vendor_name": None, "date": None,
                         "amount": None, "_source": "excel_csv"}
            for col_idx, cell in enumerate(row):
                field = col_map.get(col_idx)
                if field is None:
                    continue
                value = _cell_str(cell)
                if value and inv.get(field) is None:
                    inv[field] = value

            # Require the two fields that actually matter for matching —
            # otherwise this is a blank/decorative row, not an invoice.
            if not inv["invoice_number"] and not inv["amount"]:
                continue

            invoices.append(inv)
            sheet_count += 1

        if sheet_count:
            logger.info("Extracted %d invoices from sheet '%s'.", sheet_count, sheet_name)

    logger.info("Loaded %d total invoices from %s.", len(invoices), path.name)
    return invoices