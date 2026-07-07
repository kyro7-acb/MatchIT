"""
backend/app/services/extract.py
--------------------------------
Extract structured data from invoice images, PDFs, and structured files.

Extraction path by file type:
  • image (jpg/png)  → PP-StructureV3 layout+table analysis → rule-based field detection
  • PDF              → convert pages to images → same PP-StructureV3 path
  • Excel/CSV        → pandas (no OCR needed, used for ledger)

PP-StructureV3 replaces plain PaddleOCR:
  - Better layout analysis (separates header, body, table regions)
  - Native table recognition → structured rows/columns directly
  - Higher accuracy on mixed-content documents

Rule-based post-processing is unchanged from the original five-service design.
"""

from __future__ import annotations

import re
import sys
import io
from pathlib import Path
from typing import Any, Optional

from app.core.config import PATTERNS
from app.core.utils import get_logger, parse_amount, parse_date

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lazy singletons — PP-StructureV3 and PDF converter
# ---------------------------------------------------------------------------

_structure_instance = None
_pdf_converter      = None


def _get_structure():
    """
    Lazily initialise PP-StructureV3 (PaddleX document pipeline).
    Falls back to classic PaddleOCR if PaddleX is not installed.
    """
    try:
        from paddlex import create_pipeline  # type: ignore
        pipeline = create_pipeline(pipeline="PP-StructureV3")
        logger.info("PP-StructureV3 pipeline loaded.")
        return ("paddlex", pipeline)
    except ImportError:
        logger.warning(
            "PaddleX not found — falling back to PaddleOCR. "
            "Install with: pip install paddlex"
        )
    try:
        from paddleocr import PaddleOCR  # type: ignore
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        logger.info("PaddleOCR (fallback) loaded.")
        return ("paddleocr", ocr)
    except ImportError:
        logger.error("Neither PaddleX nor PaddleOCR is installed.")
        sys.exit(1)


def _structure():
    global _structure_instance
    if _structure_instance is None:
        _structure_instance = _get_structure()
    return _structure_instance


def _get_pdf_converter():
    try:
        import fitz  # PyMuPDF
        return fitz
    except ImportError:
        logger.warning("PyMuPDF not found. PDF support disabled. Install: pip install pymupdf")
        return None


def _pdf_lib():
    global _pdf_converter
    if _pdf_converter is None:
        _pdf_converter = _get_pdf_converter()
    return _pdf_converter


# ---------------------------------------------------------------------------
# TextBlock (unchanged from original design)
# ---------------------------------------------------------------------------

class TextBlock:
    """A single detected text region with its bounding box and text."""

    def __init__(self, text: str, bbox: list) -> None:
        self.text = text.strip()
        self.bbox = bbox

    @property
    def top_left_y(self) -> float:
        return self.bbox[0][1] if self.bbox else 0.0

    @property
    def top_left_x(self) -> float:
        return self.bbox[0][0] if self.bbox else 0.0

    def __repr__(self) -> str:
        return f"TextBlock({self.text!r})"


# ---------------------------------------------------------------------------
# PP-StructureV3 runner
# ---------------------------------------------------------------------------

def _run_structure_v3(image_path: str) -> dict:
    """
    Run PP-StructureV3 on an image.

    Returns a dict:
    {
        "blocks": list[TextBlock],          # all text blocks (sorted)
        "tables": list[list[list[str]]],    # list of tables, each table = list of rows,
                                            # each row = list of cell strings
        "raw_text": str
    }
    """
    backend_type, engine = _structure()

    if backend_type == "paddlex":
        return _parse_paddlex_result(engine, image_path)
    else:
        return _parse_paddleocr_result(engine, image_path)


def _parse_paddlex_result(pipeline, image_path: str) -> dict:
    """Parse PP-StructureV3 / PaddleX output."""
    result = pipeline.predict(image_path)

    blocks: list[TextBlock] = []
    tables: list[list[list[str]]] = []

    for page_result in result:
        # PaddleX returns layout regions; each has a type and content
        for region in page_result.get("layout_result", {}).get("boxes", []):
            region_type = region.get("label", "").lower()
            text        = region.get("text", "").strip()
            bbox        = region.get("coordinate", [[0,0],[0,0],[0,0],[0,0]])

            if region_type == "table":
                # PP-StructureV3 gives structured table HTML or cell list
                table_cells = region.get("table_result", {}).get("cells", [])
                if table_cells:
                    table_matrix = _cells_to_matrix(table_cells)
                    if table_matrix:
                        tables.append(table_matrix)
                # Also extract text from table for block list
                if text:
                    blocks.append(TextBlock(text, bbox))
            else:
                if text:
                    blocks.append(TextBlock(text, bbox))

        # Also grab raw OCR blocks if available
        for item in page_result.get("ocr_result", []):
            if item and len(item) == 2:
                bbox_raw, (txt, conf) = item
                if conf >= 0.3 and txt.strip():
                    blocks.append(TextBlock(txt, bbox_raw))

    blocks.sort(key=lambda b: (round(b.top_left_y / 10) * 10, b.top_left_x))
    raw_text = " | ".join(b.text for b in blocks)

    return {"blocks": blocks, "tables": tables, "raw_text": raw_text}


def _cells_to_matrix(cells: list[dict]) -> list[list[str]]:
    """
    Convert PP-StructureV3 cell list into a 2D list of strings.
    Each cell has row_idx, col_idx, text.
    """
    if not cells:
        return []
    max_row = max(c.get("row_end", c.get("row_idx", 0)) for c in cells)
    max_col = max(c.get("col_end", c.get("col_idx", 0)) for c in cells)
    matrix  = [[""] * (max_col + 1) for _ in range(max_row + 1)]
    for cell in cells:
        r = cell.get("row_idx", 0)
        c = cell.get("col_idx", 0)
        matrix[r][c] = cell.get("text", "").strip()
    # Remove completely empty rows
    matrix = [row for row in matrix if any(cell for cell in row)]
    return matrix


def _parse_paddleocr_result(ocr_engine, image_path: str) -> dict:
    """Fallback: parse classic PaddleOCR output into the same dict shape."""
    result = ocr_engine.ocr(image_path, cls=True)
    # Unwrap extra list for single image
    if result and isinstance(result[0], list) and result[0] and isinstance(result[0][0], list):
        result = result[0]
    result = result or []

    blocks: list[TextBlock] = []
    for item in result:
        if item is None:
            continue
        bbox, (text, confidence) = item
        if confidence >= 0.3 and text.strip():
            blocks.append(TextBlock(text, bbox))

    blocks.sort(key=lambda b: (round(b.top_left_y / 10) * 10, b.top_left_x))

    # Build table from row-grouped blocks (same as original heuristic)
    tables = _blocks_to_tables(blocks)
    raw_text = " | ".join(b.text for b in blocks)

    return {"blocks": blocks, "tables": tables, "raw_text": raw_text}


# ---------------------------------------------------------------------------
# PDF → images → extraction
# ---------------------------------------------------------------------------

def _pdf_to_images(pdf_path: str) -> list[str]:
    """
    Convert each page of a PDF to a temporary PNG file.
    Returns list of image paths.
    """
    fitz = _pdf_lib()
    if fitz is None:
        raise RuntimeError("PyMuPDF not installed — cannot process PDF files.")

    import tempfile, os
    doc        = fitz.open(pdf_path)
    image_paths = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat  = fitz.Matrix(2.0, 2.0)   # 2x scale → higher DPI for OCR
        pix  = page.get_pixmap(matrix=mat)
        tmp  = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        pix.save(tmp.name)
        image_paths.append(tmp.name)

    doc.close()
    logger.info("PDF converted to %d page images.", len(image_paths))
    return image_paths


def _cleanup_temp_images(paths: list[str]) -> None:
    import os
    for p in paths:
        try:
            os.unlink(p)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Field finders (unchanged rule-based logic from original)
# ---------------------------------------------------------------------------

def _find_by_regex(blocks: list[TextBlock], pattern: re.Pattern) -> Optional[str]:
    for block in blocks:
        m = pattern.search(block.text)
        if m:
            return m.group(1).strip()
    full_text = " ".join(b.text for b in blocks)
    m = pattern.search(full_text)
    return m.group(1).strip() if m else None


def _find_invoice_number(blocks: list[TextBlock]) -> Optional[str]:
    label_patterns = [
        re.compile(r"(?:invoice|inv|bill|doc|voucher)\s*(?:no|number|num|#)?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9/\-.]{1,20})", re.IGNORECASE),
        re.compile(r"(?:no|number|num)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9/\-.]{1,20})", re.IGNORECASE),
    ]
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        for pattern in label_patterns:
            m = pattern.search(text)
            if m:
                candidate = m.group(1).strip(" .,:;")
                if candidate and candidate.lower() not in {"invoice", "inv", "bill", "doc", "voucher", "no", "number", "num"}:
                    return candidate

    full_text = " ".join(b.text for b in blocks)
    for pattern in label_patterns:
        m = pattern.search(full_text)
        if m:
            candidate = m.group(1).strip(" .,:;")
            if candidate and candidate.lower() not in {"invoice", "inv", "bill", "doc", "voucher", "no", "number", "num"}:
                return candidate

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        if re.search(r"(?:invoice|bill|date|amount|total|due|balance|customer|phone|email|address|terms)", text, re.IGNORECASE):
            continue
        for candidate in re.findall(r"\b(?:INV|INVOICE|BILL|DOC|PO|ORDER)[-# ]?([A-Z0-9][A-Z0-9/\-.]{1,20})\b", text, re.IGNORECASE):
            return candidate.strip(" .,:;")
        for candidate in re.findall(r"\b([A-Z]{1,4}[-_/]?\d{2,8}|[A-Z0-9]{2,10}[-_/][A-Z0-9]{2,10})\b", text, re.IGNORECASE):
            if len(candidate) <= 20 and not re.search(r"^(?:date|amount|total|due|balance|invoice|bill)$", candidate, re.IGNORECASE):
                return candidate
    return None


def _find_vendor_name(blocks: list[TextBlock]) -> Optional[str]:
    keyword_re = re.compile(
        r"(?:vendor|supplier|billed\s*(?:by|to)|from|sold\s*by)\s*[:\-]?\s*(.*)",
        re.IGNORECASE,
    )
    for block in blocks:
        m = keyword_re.search(block.text)
        if m and m.group(1).strip():
            return m.group(1).strip()

    for block in blocks[:12]:
        text = block.text.strip()
        if not text:
            continue
        if re.search(r"(?:invoice|bill|date|amount|total|due|balance|customer|phone|email|address|terms|payment)", text, re.IGNORECASE):
            continue
        if len(text.split()) < 2:
            continue
        if re.match(r"^[A-Z][A-Za-z0-9&.,'()/-]+(?:\s+[A-Z][A-Za-z0-9&.,'()/-]+){0,5}$", text):
            return text

    company_re = re.compile(
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}(?:\s+(?:Pvt|Ltd|Inc|LLC|Co)\.?)?"
    )
    for block in blocks[:10]:
        m = company_re.search(block.text)
        if m and len(m.group()) > 4:
            return m.group().strip()
    return None


# ---------------------------------------------------------------------------
# Invoice extraction — public entry point
# ---------------------------------------------------------------------------

def extract_invoice(file_path: str) -> dict:
    """
    Extract structured invoice fields from an image or PDF.

    Returns
    -------
    {
        "invoice_number": str | None,
        "vendor_name":    str | None,
        "date":           str | None,
        "amount":         str | None,
        "_raw_text":      str,
        "_source":        str,  # "image" | "pdf"
    }
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_invoice_from_pdf(file_path)
    else:
        return _extract_invoice_from_image(file_path)


def _extract_invoice_from_image(image_path: str) -> dict:
    logger.info("Extracting invoice from image: %s", image_path)
    parsed = _run_structure_v3(image_path)
    blocks = parsed["blocks"]

    invoice_number = _find_invoice_number(blocks)
    vendor_name    = _find_vendor_name(blocks)
    date_str       = _find_by_regex(blocks, PATTERNS["date"])
    amount_str     = _find_by_regex(blocks, PATTERNS["amount"])
    if amount_str is None:
        amount_str = _find_by_regex(blocks, PATTERNS["currency_amount"])

    return {
        "invoice_number": invoice_number,
        "vendor_name":    vendor_name,
        "date":           date_str,
        "amount":         amount_str,
        "_raw_text":      parsed["raw_text"],
        "_source":        "image",
    }


def _extract_invoice_from_pdf(pdf_path: str) -> dict:
    logger.info("Extracting invoice from PDF: %s", pdf_path)
    image_paths = _pdf_to_images(pdf_path)
    all_blocks: list[TextBlock] = []

    try:
        for img_path in image_paths:
            parsed  = _run_structure_v3(img_path)
            all_blocks.extend(parsed["blocks"])
    finally:
        _cleanup_temp_images(image_paths)

    all_blocks.sort(key=lambda b: (round(b.top_left_y / 10) * 10, b.top_left_x))

    invoice_number = _find_invoice_number(all_blocks)
    vendor_name    = _find_vendor_name(all_blocks)
    date_str       = _find_by_regex(all_blocks, PATTERNS["date"])
    amount_str     = _find_by_regex(all_blocks, PATTERNS["amount"])
    if amount_str is None:
        amount_str = _find_by_regex(all_blocks, PATTERNS["currency_amount"])

    return {
        "invoice_number": invoice_number,
        "vendor_name":    vendor_name,
        "date":           date_str,
        "amount":         amount_str,
        "_raw_text":      " | ".join(b.text for b in all_blocks),
        "_source":        "pdf",
    }


# ---------------------------------------------------------------------------
# Ledger extraction — images/PDFs  (PP-StructureV3 table path)
# ---------------------------------------------------------------------------

def extract_ledger_from_file(file_path: str) -> list[dict]:
    """
    Extract ledger rows from image or PDF.
    PP-StructureV3 table recognition is used preferentially.
    Falls back to heuristic row-grouping if no structured tables found.
    """
    path   = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_ledger_from_pdf(file_path)
    else:
        return _extract_ledger_from_image(file_path)


def _extract_ledger_from_image(image_path: str) -> list[dict]:
    logger.info("Extracting ledger from image: %s", image_path)
    parsed = _run_structure_v3(image_path)

    # If PP-StructureV3 found structured tables, use them directly
    if parsed["tables"]:
        entries = []
        for table in parsed["tables"]:
            entries.extend(_table_matrix_to_entries(table))
        if entries:
            logger.info("Extracted %d ledger rows via table recognition.", len(entries))
            return entries

    # Fallback: heuristic row-grouping on text blocks
    logger.info("No structured tables found — using heuristic row grouping.")
    rows = _group_blocks_into_rows(parsed["blocks"])
    return _rows_to_ledger_entries(rows)


def _extract_ledger_from_pdf(pdf_path: str) -> list[dict]:
    logger.info("Extracting ledger from PDF: %s", pdf_path)
    image_paths = _pdf_to_images(pdf_path)
    all_entries: list[dict] = []

    try:
        for img_path in image_paths:
            parsed = _run_structure_v3(img_path)
            if parsed["tables"]:
                for table in parsed["tables"]:
                    all_entries.extend(_table_matrix_to_entries(table))
            else:
                rows = _group_blocks_into_rows(parsed["blocks"])
                all_entries.extend(_rows_to_ledger_entries(rows))
    finally:
        _cleanup_temp_images(image_paths)

    logger.info("Extracted %d total ledger rows from PDF.", len(all_entries))
    return all_entries


def _table_matrix_to_entries(matrix: list[list[str]]) -> list[dict]:
    """
    Convert a 2D cell matrix (from PP-StructureV3) into ledger entry dicts.
    Detects header row and maps columns to semantic names.
    """
    if len(matrix) < 2:
        return []

    # Find header row (first row with ≥2 known keywords)
    header_keywords = {"reference", "ref", "date", "debit", "credit", "amount", "vendor", "description"}
    header_idx = 0
    for i, row in enumerate(matrix):
        row_lower = {cell.lower() for cell in row}
        if len(row_lower & header_keywords) >= 2:
            header_idx = i
            break

    header_row = matrix[header_idx]
    col_map: dict[int, str] = {}
    for col_idx, cell in enumerate(header_row):
        col_map[col_idx] = _classify_column(cell)

    entries: list[dict] = []
    for row in matrix[header_idx + 1:]:
        entry: dict = {"reference": None, "vendor": None, "date": None, "debit": None, "credit": None}
        for col_idx, cell in enumerate(row):
            col_name = col_map.get(col_idx, "other")
            if col_name in entry and cell.strip():
                entry[col_name] = cell.strip()
        if any(v for v in entry.values()):
            entries.append(entry)

    return entries


def _classify_column(header_text: str) -> str:
    h = header_text.lower()
    if re.search(r"ref|invoice|voucher|doc", h):     return "reference"
    if re.search(r"vendor|supplier|party|name", h):  return "vendor"
    if re.search(r"date", h):                         return "date"
    if re.search(r"debit|dr\b", h):                  return "debit"
    if re.search(r"credit|cr\b", h):                 return "credit"
    if re.search(r"amount|amt|total", h):             return "amount"
    return "other"


# ---------------------------------------------------------------------------
# Heuristic helpers (retained from original extract.py)
# ---------------------------------------------------------------------------

def _group_blocks_into_rows(blocks: list[TextBlock], tolerance: float = 15.0) -> list[list[TextBlock]]:
    if not blocks:
        return []
    rows: list[list[TextBlock]] = []
    current_row = [blocks[0]]
    current_y   = blocks[0].top_left_y

    for block in blocks[1:]:
        if abs(block.top_left_y - current_y) <= tolerance:
            current_row.append(block)
        else:
            rows.append(sorted(current_row, key=lambda b: b.top_left_x))
            current_row = [block]
            current_y   = block.top_left_y

    rows.append(sorted(current_row, key=lambda b: b.top_left_x))
    return rows


def _rows_to_ledger_entries(rows: list[list[TextBlock]]) -> list[dict]:
    """
    Heuristic fallback: detect header row, build column map, fill entries.
    Identical logic to original extract.py with unified column classifier.
    """
    header_keywords = {"reference","ref","date","debit","credit","amount","description","narration"}
    header_idx = None
    for idx, row in enumerate(rows):
        row_text = {b.text.lower() for b in row}
        if len(row_text & header_keywords) >= 2:
            header_idx = idx
            break

    if header_idx is None:
        return _positional_ledger_extract(rows)

    col_map: dict[int, str] = {}
    for col_idx, block in enumerate(rows[header_idx]):
        col_map[col_idx] = _classify_column(block.text)

    entries: list[dict] = []
    for row in rows[header_idx + 1:]:
        entry: dict = {"reference": None, "vendor": None, "date": None, "debit": None, "credit": None}
        for col_idx, block in enumerate(row):
            col_name = col_map.get(col_idx, "other")
            if col_name in entry:
                entry[col_name] = block.text
        if any(v for v in entry.values()):
            entries.append(entry)

    return entries


def _positional_ledger_extract(rows: list[list[TextBlock]]) -> list[dict]:
    entries: list[dict] = []
    for row in rows:
        texts = [b.text for b in row]
        if len(texts) < 2:
            continue
        reference = vendor = date_val = debit = credit = None
        for text in texts:
            if PATTERNS["date"].search(text):
                date_val = text
            elif PATTERNS["amount"].search(text) or re.match(r"[\d,]+\.\d{2}$", text):
                if debit is None:
                    debit = text
                else:
                    credit = text
            elif re.match(r"[A-Z]{2,}\d{4,}", text):
                reference = text
            elif len(text) > 3 and not reference:
                vendor = text
        entry = {"reference": reference, "vendor": vendor,
                 "date": date_val, "debit": debit, "credit": credit}
        if any(v for v in entry.values()):
            entries.append(entry)
    return entries


def _blocks_to_tables(blocks: list[TextBlock]) -> list[list[list[str]]]:
    """Convert block list to table matrix via heuristic row grouping (fallback)."""
    rows = _group_blocks_into_rows(blocks)
    if not rows:
        return []
    matrix = [[b.text for b in row] for row in rows]
    return [matrix] if matrix else []


# ---------------------------------------------------------------------------
# Pandas extraction (Excel / CSV ledger)
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
# classification. Matching is substring-based (not exact equality) so
# "Debit Amount", "debit amt", "DR" etc. all resolve to "debit".
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


def _cell_str(cell: Any) -> str:
    """Safely stringify a raw pandas cell, treating NaN/NaT/None as empty."""
    import pandas as pd
    if cell is None:
        return ""
    try:
        if pd.isna(cell):
            return ""
    except (TypeError, ValueError):
        pass
    return str(cell).strip()


def _normalize_header_cell(cell: Any) -> str:
    return re.sub(r"\s+", " ", _cell_str(cell)).lower()


def _classify_ledger_header_cell(cell: Any) -> Optional[str]:
    """Map a single raw header cell to a semantic field name, or None."""
    h = _normalize_header_cell(cell)
    if not h:
        return None
    for field, keywords in _LEDGER_COLUMN_KEYWORDS.items():
        # Running-total / carry-forward columns ("Opening Amount",
        # "Balance Amount") are not per-transaction debit/credit figures —
        # skip them so they don't get swept up by the generic "amount"
        # keyword and mistakenly used as a debit/credit fallback.
        if field == "amount" and ("opening" in h or "balance" in h):
            continue
        for kw in keywords:
            if kw.strip() and kw.strip() in h:
                return field
    return None


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
    import pandas as pd

    path   = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        sheets = pd.read_excel(file_path, sheet_name=None, header=None, dtype=object)
    elif suffix == ".csv":
        sheets = {"csv": pd.read_csv(file_path, header=None, dtype=object)}
    else:
        raise ValueError(f"Unsupported structured file format: {suffix}")

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
    "date":           ["invoice date", "bill date"],
    "amount":         ["grand total", "net amount", "invoice amount", "total amount"],
}

# Labels that must never be treated as a match for the field above, even
# though they share a word (e.g. "Invoice Miti" is a Bikram Sambat date,
# not the Gregorian date we want; "Customer" is the buyer, not the vendor).
_INVOICE_FORM_LABEL_EXCLUDES: dict[str, list[str]] = {
    "date": ["miti"],
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
    if not h:
        return None
    for field, keywords in _INVOICE_COLUMN_KEYWORDS.items():
        for kw in keywords:
            if kw.strip() and kw.strip() in h:
                return field
    return None


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
    import pandas as pd

    path   = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        sheets = pd.read_excel(file_path, sheet_name=None, header=None, dtype=object)
    elif suffix == ".csv":
        sheets = {"csv": pd.read_csv(file_path, header=None, dtype=object)}
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

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