from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Optional

from config import PATTERNS
from utils import get_logger, parse_amount, parse_date

logger = get_logger(__name__)


# Returns PaddleOCR instance (lazy import)
def _get_ocr():
    
    try:
        from paddleocr import PaddleOCR  # type: ignore
        return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    except ImportError:
        logger.error(
            "PaddleOCR is not installed. Run: pip install paddleocr paddlepaddle"
        )
        sys.exit(1)

_ocr_instance = None

# PaddleOCR instance initializer
def _ocr():
    
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = _get_ocr()
    return _ocr_instance

# OCR's messy result to Tidy result
class TextBlock:
    
    def __init__(self, text: str, bbox: list[list[float]]) -> None:
        self.text: str = text.strip()
        self.bbox: list[list[float]] = bbox  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]

    @property
    def top_left_y(self) -> float:
        return self.bbox[0][1]

    @property
    def top_left_x(self) -> float:
        return self.bbox[0][0]

    def __repr__(self) -> str:  # pragma: no cover
        return f"TextBlock({self.text!r})"

# Core OCR runner
def run_paddle_ocr(image_path: str) -> list[Any]:
    
    logger.info("Running PaddleOCR on: %s", image_path)
    result = _ocr().ocr(image_path, cls=True) # cls=True means "also run the angle classifier"
    
    # PaddleOCR wraps results in an extra list when processing single images
    if result and isinstance(result[0], list) and result[0] and isinstance(result[0][0], list):
        return result[0]
    return result or []

# Extracts text from the OCR's result
def extract_text_blocks(ocr_result: list[Any]) -> list[TextBlock]:
    
    blocks: list[TextBlock] = []
    for item in ocr_result:
        if item is None:
            continue
        bbox, (text, confidence) = item
        if confidence < 0.3:          # discard very low-confidence detections
            continue
        blocks.append(TextBlock(text, bbox))

    # Sort by vertical position then horizontal
    blocks.sort(key=lambda b: (round(b.top_left_y / 10) * 10, b.top_left_x))
    return blocks


# Field finders using regular expression
def _find_by_regex(blocks: list[TextBlock], pattern: re.Pattern) -> Optional[str]:
    
    for block in blocks:
        m = pattern.search(block.text)
        if m:
            return m.group(1).strip()

    full_text = " ".join(b.text for b in blocks)
    m = pattern.search(full_text)
    return m.group(1).strip() if m else None

# Field finders — vendor
def _find_vendor_name(blocks: list[TextBlock]) -> Optional[str]:
    
    keyword_re = re.compile(
        r"(?:vendor|supplier|billed\s*(?:by|to)|from|sold\s*by)\s*[:\-]?\s*(.*)",
        re.IGNORECASE,
    )
    for block in blocks:
        m = keyword_re.search(block.text)
        if m and m.group(1).strip():
            return m.group(1).strip()

    # Layout fallback: first 10 blocks, pick one that looks like a company name
    company_re = re.compile(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}(?:\s+(?:Pvt|Ltd|Inc|LLC|Co)\.?)?")
    for block in blocks[:10]:
        m = company_re.search(block.text)
        if m and len(m.group()) > 4:
            return m.group().strip()
    return None

# Invoice extraction
def extract_invoice(image_path: str) -> dict:
    
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    ocr_result = run_paddle_ocr(image_path)
    blocks = extract_text_blocks(ocr_result)

    invoice_number = _find_by_regex(blocks, PATTERNS["invoice_number"])
    vendor_name    = _find_vendor_name(blocks)
    date_str       = _find_by_regex(blocks, PATTERNS["date"])
    amount_str     = _find_by_regex(blocks, PATTERNS["amount"])

    # Last-resort amount: any currency-prefixed number
    if amount_str is None:
        amount_str = _find_by_regex(blocks, PATTERNS["currency_amount"])

    raw_text = " | ".join(b.text for b in blocks)
    logger.debug("Raw OCR text: %s", raw_text)

    return {
        "invoice_number": invoice_number,
        "vendor_name":    vendor_name,
        "date":           date_str,
        "amount":         amount_str,
        "_raw_text":      raw_text,
    }

# Group TextBlocks that share approximately the same vertical position into logical rows (for table reconstruction).
def _group_blocks_into_rows(
    blocks: list[TextBlock], row_tolerance: float = 15.0
) -> list[list[TextBlock]]:
    
    if not blocks:
        return []

    rows: list[list[TextBlock]] = []
    current_row: list[TextBlock] = [blocks[0]]
    current_y = blocks[0].top_left_y

    for block in blocks[1:]:
        if abs(block.top_left_y - current_y) <= row_tolerance:
            current_row.append(block)
        else:
            rows.append(sorted(current_row, key=lambda b: b.top_left_x))
            current_row = [block]
            current_y = block.top_left_y

    rows.append(sorted(current_row, key=lambda b: b.top_left_x))
    return rows

# Extract ledger table headers
def _detect_header_row(rows: list[list[TextBlock]]) -> Optional[int]:

    header_keywords = {"reference", "ref", "date", "debit", "credit", "amount", "description", "narration"}
    for idx, row in enumerate(rows):
        row_text = {b.text.lower() for b in row}
        overlap = row_text & header_keywords
        if len(overlap) >= 2:
            return idx
    return None

# Maps header cell to a semantic column name
def _classify_column_by_header(header_text: str) -> str:
    
    h = header_text.lower()
    if re.search(r"ref|invoice|voucher|doc|reference", h):
        return "reference"
    if re.search(r"vendor|supplier|party|name", h):
        return "vendor"
    if re.search(r"date", h):
        return "date"
    if re.search(r"debit|dr\b", h):
        return "debit"
    if re.search(r"credit|cr\b", h):
        return "credit"
    if re.search(r"amount|amt|total", h):
        return "amount"
    return "other"

# Ledger extraction (tabular)
def extract_ledger(image_path: str) -> list[dict]:
    
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    ocr_result = run_paddle_ocr(image_path)
    blocks = extract_text_blocks(ocr_result)
    rows = _group_blocks_into_rows(blocks)

    header_idx = _detect_header_row(rows)
    if header_idx is None:
        logger.warning("Could not detect ledger header row; attempting positional extraction.")
        return _positional_ledger_extract(rows)

    header_row = rows[header_idx]
    # Map column index → semantic name
    col_map: dict[int, str] = {}
    for col_idx, block in enumerate(header_row):
        col_map[col_idx] = _classify_column_by_header(block.text)

    entries: list[dict] = []
    for row in rows[header_idx + 1:]:
        if not row:
            continue
        entry: dict[str, Optional[str]] = {
            "reference": None, "vendor": None,
            "date": None, "debit": None, "credit": None,
        }
        for col_idx, block in enumerate(row):
            col_name = col_map.get(col_idx, "other")
            if col_name in entry:
                entry[col_name] = block.text
        # Skip completely empty rows
        if all(v is None for v in entry.values()):
            continue
        entries.append(entry)

    logger.info("Extracted %d ledger rows.", len(entries))
    return entries

# Ledger extraction (positional) only used when no recognisable header
def _positional_ledger_extract(rows: list[list[TextBlock]]) -> list[dict]:
    
    entries: list[dict] = []
    for row in rows:
        texts = [b.text for b in row]
        if len(texts) < 2:
            continue

        # Try to classify each cell
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

        entry = {
            "reference": reference,
            "vendor": vendor,
            "date": date_val,
            "debit": debit,
            "credit": credit,
        }
        if any(v is not None for v in entry.values()):
            entries.append(entry)

    return entries
