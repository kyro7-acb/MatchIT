"""
backend/app/services/matching_service.py
-----------------------------------------
Orchestrates the full matching pipeline:
  extract → preprocess → candidate_filter → score → optimize → classify

Additionally:
  - Records skipped items with reasons
  - Builds field-level explainability breakdown for every match
  - Persists everything to PostgreSQL
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import UPLOAD_DIR
from app.core.utils import get_logger, compute_field_breakdown
from app.db.models import (
    UploadSession, Invoice, LedgerEntry,
    MatchResultDB, SkippedItem, MatchStatus,
)
from app.models.schemas import (
    MatchResponse, MatchedPair, MatchSummary, SkippedItem as SkippedSchema,
    ExtractedInvoice, ExtractedLedgerEntry, FieldBreakdown, FieldScore,
)
from app.services.preprocess import preprocess_invoices, preprocess_ledger
from app.services.similarity import build_score_matrix
from app.services.optimizer import optimize_matches, filter_candidates
from app.services.classifier import classify_matches, classify

logger = get_logger(__name__)


async def run_full_pipeline(
    session_id: str,
    db: AsyncSession,
) -> MatchResponse:
    """
    Run the complete matching pipeline for a session.
    Invoices and ledger entries must already be saved in DB for this session.
    """
    # ── 1. Load from DB ──────────────────────────────────────────────────
    inv_rows = (await db.execute(
        select(Invoice).where(Invoice.session_id == session_id)
    )).scalars().all()

    led_rows = (await db.execute(
        select(LedgerEntry).where(LedgerEntry.session_id == session_id)
    )).scalars().all()

    if not inv_rows:
        raise ValueError("No invoices found for this session.")
    if not led_rows:
        raise ValueError("No ledger entries found for this session.")

    # ── 2. Convert ORM rows → dicts for the service layer ────────────────
    raw_invoices = [_invoice_orm_to_dict(r) for r in inv_rows]
    raw_ledger   = [_ledger_orm_to_dict(r)  for r in led_rows]

    # ── 3. Preprocess ─────────────────────────────────────────────────────
    logger.info("[%s] Preprocessing %d invoices, %d ledger entries.",
                session_id, len(raw_invoices), len(raw_ledger))
    invoices = preprocess_invoices(raw_invoices)
    ledger   = preprocess_ledger(raw_ledger)

    # ── 4. Candidate filtering ────────────────────────────────────────────
    filtered_invoices, filtered_ledger = filter_candidates(invoices, ledger)

    skipped_items: list[SkippedSchema] = []

    # Record skipped ledger entries
    filtered_refs = {e.get("reference") for e in filtered_ledger}
    for entry in ledger:
        if entry.get("reference") not in filtered_refs:
            skipped_items.append(SkippedSchema(
                item_type="ledger_entry",
                item_ref=entry.get("reference"),
                reason="Date too far from any invoice date (±60 day window)",
                detail={"date": str(entry.get("parsed_date", ""))},
            ))

    # ── 5. Score matrix ───────────────────────────────────────────────────
    logger.info("[%s] Building %dx%d score matrix.",
                session_id, len(filtered_invoices), len(filtered_ledger))
    score_matrix = build_score_matrix(filtered_invoices, filtered_ledger)

    # ── 6. Hungarian optimisation ─────────────────────────────────────────
    raw_matches = optimize_matches(score_matrix)

    # ── 7. Classification ─────────────────────────────────────────────────
    classified  = classify_matches(raw_matches, filtered_invoices, filtered_ledger)

    # ── 8. Build rich response + persist to DB ────────────────────────────
    matched_pairs: list[MatchedPair] = []

    for result in classified:
        inv_dict = filtered_invoices[result["invoice_idx"]]
        led_dict = filtered_ledger[result["ledger_idx"]]

        # Find ORM rows by normalised key
        inv_orm = next(
            (r for r in inv_rows
             if (r.invoice_number or "") == (inv_dict.get("invoice_number") or "")),
            inv_rows[result["invoice_idx"]] if result["invoice_idx"] < len(inv_rows) else inv_rows[0]
        )
        led_orm = next(
            (r for r in led_rows
             if (r.reference or "") == (led_dict.get("reference") or "")),
            led_rows[result["ledger_idx"]] if result["ledger_idx"] < len(led_rows) else led_rows[0]
        )

        breakdown_raw = compute_field_breakdown(inv_dict, led_dict)
        breakdown     = FieldBreakdown(
            invoice_number=FieldScore(**breakdown_raw["invoice_number"]),
            vendor=FieldScore(**breakdown_raw["vendor"]),
            date=FieldScore(**breakdown_raw["date"]),
            amount=FieldScore(**breakdown_raw["amount"]),
        )

        status_str = result["status"]

        # Persist match to DB
        match_db = MatchResultDB(
            id              = str(uuid.uuid4()),
            session_id      = session_id,
            invoice_id      = inv_orm.id,
            ledger_entry_id = led_orm.id,
            score           = result["score"],
            status          = MatchStatus(status_str),
            field_breakdown = breakdown_raw,
        )
        db.add(match_db)

        # Add unmatched invoices to skipped
        if status_str == "unmatched":
            skipped_items.append(SkippedSchema(
                item_type="invoice",
                item_ref=inv_dict.get("invoice_number"),
                reason=f"Best similarity score ({result['score']:.3f}) below review threshold",
                detail={"score": result["score"], "best_ledger_ref": led_dict.get("reference")},
            ))

        matched_pairs.append(MatchedPair(
            match_id        = match_db.id,
            invoice         = ExtractedInvoice(
                id             = inv_orm.id,
                source_file    = inv_orm.source_file,
                invoice_number = inv_orm.invoice_number,
                vendor_name    = inv_orm.vendor_name,
                date           = inv_orm.date,
                amount         = inv_orm.amount,
                parsed_date    = inv_orm.parsed_date,
                parsed_amount  = inv_orm.parsed_amount,
            ),
            ledger_entry    = ExtractedLedgerEntry(
                id            = led_orm.id,
                source_file   = led_orm.source_file,
                reference     = led_orm.reference,
                vendor        = led_orm.vendor,
                date          = led_orm.date,
                debit         = led_orm.debit,
                credit        = led_orm.credit,
                parsed_date   = led_orm.parsed_date,
                debit_amount  = led_orm.debit_amount,
                credit_amount = led_orm.credit_amount,
            ),
            score           = result["score"],
            status          = status_str,
            field_breakdown = breakdown,
        ))

    # Persist skipped items
    for sk in skipped_items:
        db.add(SkippedItem(
            id         = str(uuid.uuid4()),
            session_id = session_id,
            item_type  = sk.item_type,
            item_ref   = sk.item_ref,
            reason     = sk.reason,
            detail     = sk.detail,
        ))

    # Update session status
    session_row = await db.get(UploadSession, session_id)
    if session_row:
        session_row.status = "done"

    await db.flush()

    # ── 9. Build summary ──────────────────────────────────────────────────
    auto   = sum(1 for p in matched_pairs if p.status == "auto_match")
    review = sum(1 for p in matched_pairs if p.status == "review")
    unmatched = sum(1 for p in matched_pairs if p.status == "unmatched")

    summary = MatchSummary(
        total_invoices   = len(inv_rows),
        total_ledger     = len(led_rows),
        auto_match_count = auto,
        review_count     = review,
        unmatched_count  = unmatched,
        skipped_count    = len(skipped_items),
    )

    logger.info(
        "[%s] Matching done. auto=%d review=%d unmatched=%d skipped=%d",
        session_id, auto, review, unmatched, len(skipped_items),
    )

    return MatchResponse(
        session_id = session_id,
        summary    = summary,
        matches    = matched_pairs,
        skipped    = skipped_items,
        created_at = datetime.utcnow(),
    )


async def get_cached_result(session_id: str, db: AsyncSession) -> Optional[MatchResponse]:
    """Load previously computed results from DB (cache layer)."""
    session_row = await db.get(UploadSession, session_id)
    if not session_row or session_row.status != "done":
        return None

    match_rows = (await db.execute(
        select(MatchResultDB)
        .where(MatchResultDB.session_id == session_id)
    )).scalars().all()

    if not match_rows:
        return None

    inv_rows = (await db.execute(
        select(Invoice).where(Invoice.session_id == session_id)
    )).scalars().all()
    led_rows = (await db.execute(
        select(LedgerEntry).where(LedgerEntry.session_id == session_id)
    )).scalars().all()

    inv_map = {r.id: r for r in inv_rows}
    led_map = {r.id: r for r in led_rows}

    matched_pairs: list[MatchedPair] = []
    for mr in match_rows:
        inv_orm = inv_map.get(mr.invoice_id)
        led_orm = led_map.get(mr.ledger_entry_id)
        if not inv_orm or not led_orm:
            continue

        bd_raw = mr.field_breakdown or {}
        breakdown = FieldBreakdown(
            invoice_number=FieldScore(**bd_raw.get("invoice_number", {"score":0,"weight":0.4,"contribution":0,"invoice_value":"","ledger_value":""})),
            vendor=FieldScore(**bd_raw.get("vendor", {"score":0,"weight":0.25,"contribution":0,"invoice_value":"","ledger_value":""})),
            date=FieldScore(**bd_raw.get("date", {"score":0,"weight":0.2,"contribution":0,"invoice_value":"","ledger_value":""})),
            amount=FieldScore(**bd_raw.get("amount", {"score":0,"weight":0.15,"contribution":0,"invoice_value":"","ledger_value":""})),
        )

        matched_pairs.append(MatchedPair(
            match_id        = mr.id,
            invoice         = ExtractedInvoice(
                id=inv_orm.id, source_file=inv_orm.source_file,
                invoice_number=inv_orm.invoice_number, vendor_name=inv_orm.vendor_name,
                date=inv_orm.date, amount=inv_orm.amount,
                parsed_date=inv_orm.parsed_date, parsed_amount=inv_orm.parsed_amount,
            ),
            ledger_entry    = ExtractedLedgerEntry(
                id=led_orm.id, source_file=led_orm.source_file,
                reference=led_orm.reference, vendor=led_orm.vendor,
                date=led_orm.date, debit=led_orm.debit, credit=led_orm.credit,
                parsed_date=led_orm.parsed_date,
                debit_amount=led_orm.debit_amount, credit_amount=led_orm.credit_amount,
            ),
            score           = mr.score,
            status          = mr.override_status or mr.status.value,
            field_breakdown = breakdown,
            is_overridden   = mr.is_overridden,
            override_status = mr.override_status,
            override_note   = mr.override_note,
        ))

    skipped_rows = (await db.execute(
        select(SkippedItem).where(SkippedItem.session_id == session_id)
    )).scalars().all()

    skipped = [
        SkippedSchema(item_type=s.item_type, item_ref=s.item_ref,
                      reason=s.reason, detail=s.detail)
        for s in skipped_rows
    ]

    auto      = sum(1 for p in matched_pairs if (p.override_status or p.status) == "auto_match")
    review    = sum(1 for p in matched_pairs if (p.override_status or p.status) == "review")
    unmatched = sum(1 for p in matched_pairs if (p.override_status or p.status) == "unmatched")

    return MatchResponse(
        session_id = session_id,
        summary    = MatchSummary(
            total_invoices=len(inv_rows), total_ledger=len(led_rows),
            auto_match_count=auto, review_count=review,
            unmatched_count=unmatched, skipped_count=len(skipped),
        ),
        matches    = matched_pairs,
        skipped    = skipped,
        created_at = session_row.created_at,
    )


# ---------------------------------------------------------------------------
# ORM → dict helpers
# ---------------------------------------------------------------------------

def _invoice_orm_to_dict(r: Invoice) -> dict:
    return {
        "invoice_number": r.invoice_number,
        "vendor_name":    r.vendor_name,
        "date":           r.date,
        "amount":         r.amount,
        "_db_id":         r.id,
    }


def _ledger_orm_to_dict(r: LedgerEntry) -> dict:
    return {
        "reference": r.reference,
        "vendor":    r.vendor,
        "date":      r.date,
        "debit":     r.debit,
        "credit":    r.credit,
        "_db_id":    r.id,
    }
