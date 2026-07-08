import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import UPLOAD_DIR
from app.core.utils import get_logger, parse_date, parse_amount
from app.db.session import get_db
from app.db.models import UploadSession, Invoice, LedgerEntry
from app.models.schemas import UploadResponse, ExtractedInvoice, ExtractedLedgerEntry
from app.utils.file_validator import validate_and_save
from app.services.preprocess import normalize_reference, normalize_vendor

from app.services.extract import (
    extract_invoice,
    extract_ledger_from_file,
    extract_ledger_from_dataframe,
    extract_invoices_from_dataframe,
)

router = APIRouter()
logger = get_logger(__name__)

# POST /api/upload-invoice
@router.post("/upload-invoice", response_model=UploadResponse)
async def upload_invoice(
    files: List[UploadFile] = File(...),
    db:    AsyncSession     = Depends(get_db),
):
    session_id  = str(uuid.uuid4())
    session_dir = UPLOAD_DIR / session_id / "invoices"

    session_row = UploadSession(
        id            = session_id,
        invoice_files = [f.filename for f in files],
    )
    db.add(session_row)
    await db.flush()

    extracted: list[ExtractedInvoice] = []

    for upload in files:
        try:
            saved_path, file_type = await validate_and_save(upload, session_dir)
            logger.info("Invoice upload saved: %s (%s)", saved_path.name, file_type)

            if file_type in ("image", "pdf"):
                raw_list = [extract_invoice(str(saved_path))]
            else:  # excel / csv
                raw_list = extract_invoices_from_dataframe(str(saved_path))

            for raw in raw_list:
                inv_id = str(uuid.uuid4())
                pd_date   = parse_date(raw.get("date") or "")
                pd_amount = parse_amount(raw.get("amount") or "")

                orm = Invoice(
                    id                        = inv_id,
                    session_id                = session_id,
                    source_file               = upload.filename,
                    invoice_number            = raw.get("invoice_number"),
                    vendor_name               = raw.get("vendor_name"),
                    date                      = raw.get("date"),
                    amount                    = raw.get("amount"),
                    parsed_date               = pd_date,
                    parsed_amount             = pd_amount,
                    normalized_invoice_number = normalize_reference(raw.get("invoice_number") or ""),
                    normalized_vendor         = normalize_vendor(raw.get("vendor_name") or ""),
                    raw_text                  = raw.get("_raw_text"),
                )
                db.add(orm)

                extracted.append(ExtractedInvoice(
                    id             = inv_id,
                    source_file    = upload.filename,
                    invoice_number = raw.get("invoice_number"),
                    vendor_name    = raw.get("vendor_name"),
                    date           = raw.get("date"),
                    amount         = raw.get("amount"),
                    parsed_date    = pd_date,
                    parsed_amount  = pd_amount,
                ))

        except Exception as e:
            logger.error("Failed to process invoice file %s: %s", upload.filename, e)
            raise HTTPException(status_code=422, detail=f"Error processing '{upload.filename}': {e}")

    await db.flush()

    return UploadResponse(
        session_id = session_id,
        message    = f"Successfully extracted {len(extracted)} invoice(s).",
        count      = len(extracted),
        items      = extracted,
    )


# POST /api/upload-ledger
@router.post("/upload-ledger", response_model=UploadResponse)
async def upload_ledger(
    session_id: str,
    files:      List[UploadFile] = File(...),
    db:         AsyncSession     = Depends(get_db),
):

    session_row = await db.get(UploadSession, session_id)
    if not session_row:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    session_dir = UPLOAD_DIR / session_id / "ledger"
    session_row.ledger_files = [f.filename for f in files]

    extracted: list[ExtractedLedgerEntry] = []

    for upload in files:
        try:
            saved_path, file_type = await validate_and_save(upload, session_dir)
            logger.info("Ledger upload saved: %s (%s)", saved_path.name, file_type)

            if file_type in ("excel", "csv"):
                raw_list = extract_ledger_from_dataframe(str(saved_path))
            else:
                raw_list = extract_ledger_from_file(str(saved_path))

            for raw in raw_list:
                led_id    = str(uuid.uuid4())
                pd_date   = parse_date(raw.get("date") or "")
                debit_amt = parse_amount(raw.get("debit") or "")
                credit_amt= parse_amount(raw.get("credit") or "")

                orm = LedgerEntry(
                    id                   = led_id,
                    session_id           = session_id,
                    source_file          = upload.filename,
                    reference            = raw.get("reference"),
                    vendor               = raw.get("vendor"),
                    date                 = raw.get("date"),
                    debit                = raw.get("debit"),
                    credit               = raw.get("credit"),
                    parsed_date          = pd_date,
                    debit_amount         = debit_amt,
                    credit_amount        = credit_amt,
                    normalized_reference = normalize_reference(raw.get("reference") or ""),
                    normalized_vendor    = normalize_vendor(raw.get("vendor") or ""),
                )
                db.add(orm)

                extracted.append(ExtractedLedgerEntry(
                    id            = led_id,
                    source_file   = upload.filename,
                    reference     = raw.get("reference"),
                    vendor        = raw.get("vendor"),
                    date          = raw.get("date"),
                    debit         = raw.get("debit"),
                    credit        = raw.get("credit"),
                    parsed_date   = pd_date,
                    debit_amount  = debit_amt,
                    credit_amount = credit_amt,
                ))

        except Exception as e:
            logger.error("Failed to process ledger file %s: %s", upload.filename, e)
            raise HTTPException(status_code=422, detail=f"Error processing '{upload.filename}': {e}")

    await db.flush()

    return UploadResponse(
        session_id = session_id,
        message    = f"Successfully extracted {len(extracted)} ledger entry/entries.",
        count      = len(extracted),
        items      = extracted,
    )
