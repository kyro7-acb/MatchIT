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


def _find_vendor_name(blocks: list[TextBlock]) -> Optional[str]:
    keyword_re = re.compile(
        r"(?:vendor|supplier|billed\s*(?:by|to)|from|sold\s*by)\s*[:\-]?\s*(.*)",
        re.IGNORECASE,
    )
    for block in blocks:
        m = keyword_re.search(block.text)
        if m and m.group(1).strip():
            return m.group(1).strip()
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

    invoice_number = _find_by_regex(blocks, PATTERNS["invoice_number"])
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

    invoice_number = _find_by_regex(all_blocks, PATTERNS["invoice_number"])
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

def extract_ledger_from_dataframe(file_path: str) -> list[dict]:
    """
    Load a structured Excel or CSV ledger file using pandas.
    No OCR needed — columns are already structured.

    Expected columns (flexible, case-insensitive):
        reference / ref / invoice_no
        vendor / supplier / party / name
        date
        debit / dr
        credit / cr
        amount (used as debit if debit column absent)
    """
    import pandas as pd

    path   = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    elif suffix == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    else:
        raise ValueError(f"Unsupported structured file format: {suffix}")

    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.fillna("")

    col_aliases = {
        "reference": ["reference", "ref", "invoice_no", "invoice no", "voucher", "doc no"],
        "vendor":    ["vendor", "supplier", "party", "name", "vendor name"],
        "date":      ["date", "invoice date", "txn date", "transaction date"],
        "debit":     ["debit", "dr", "debit amount"],
        "credit":    ["credit", "cr", "credit amount"],
        "amount":    ["amount", "amt", "total", "net amount"],
    }

    def _find_col(aliases: list[str]) -> Optional[str]:
        for alias in aliases:
            if alias in df.columns:
                return alias
        return None

    col_map = {field: _find_col(aliases) for field, aliases in col_aliases.items()}

    entries: list[dict] = []
    for _, row in df.iterrows():
        def _val(field: str) -> Optional[str]:
            col = col_map.get(field)
            if col and col in df.columns:
                v = str(row[col]).strip()
                return v if v else None
            return None

        debit_val  = _val("debit")
        credit_val = _val("credit")
        # If no debit column, use generic amount column
        if debit_val is None and col_map.get("amount"):
            debit_val = _val("amount")

        entry = {
            "reference": _val("reference"),
            "vendor":    _val("vendor"),
            "date":      _val("date"),
            "debit":     debit_val,
            "credit":    credit_val,
        }
        if any(v for v in entry.values()):
            entries.append(entry)

    logger.info("Loaded %d rows from %s via pandas.", len(entries), path.name)
    return entries


def extract_invoices_from_dataframe(file_path: str) -> list[dict]:
    """
    Load invoices from an Excel or CSV file.
    Each row = one invoice.
    """
    import pandas as pd

    path   = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    elif suffix == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.fillna("")

    col_aliases = {
        "invoice_number": ["invoice_number", "invoice no", "inv no", "invoice_no", "number"],
        "vendor_name":    ["vendor_name", "vendor", "supplier", "party"],
        "date":           ["date", "invoice_date"],
        "amount":         ["amount", "total", "amt", "total_amount", "net_amount"],
    }

    def _find_col(aliases):
        for a in aliases:
            if a in df.columns:
                return a
        return None

    col_map = {field: _find_col(aliases) for field, aliases in col_aliases.items()}

    invoices: list[dict] = []
    for _, row in df.iterrows():
        def _val(field):
            col = col_map.get(field)
            if col and col in df.columns:
                v = str(row[col]).strip()
                return v if v else None
            return None

        inv = {
            "invoice_number": _val("invoice_number"),
            "vendor_name":    _val("vendor_name"),
            "date":           _val("date"),
            "amount":         _val("amount"),
            "_source":        "excel_csv",
        }
        if any(v for v in inv.values() if v and not v.startswith("_")):
            invoices.append(inv)

    logger.info("Loaded %d invoices from %s.", len(invoices), path.name)
    return invoices
