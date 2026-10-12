from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import CANDIDATE_WINDOW_DAYS, WEIGHTS
from app.core.utils import get_logger
from app.db.models import (
    UploadSession, Invoice, LedgerEntry,
    MatchResultDB, SkippedItem, MatchStatus,
)
from app.models.schemas import (
    MatchResponse, MatchedPair, MatchSummary, SkippedItem as SkippedSchema,
    ExtractedInvoice, ExtractedLedgerEntry, FieldBreakdown, FieldScore,
)
from app.services.preprocess import preprocess_invoices, preprocess_ledger
from app.services.similarity import build_score_matrix, compute_field_breakdown
from app.services.optimizer import optimize_matches, filter_candidates
from app.services.classifier import classify_matches

logger = get_logger(__name__)


async def run_full_pipeline(
    session_id: str,
    db: AsyncSession,
) -> MatchResponse:
    """
    Run the complete matching pipeline for a session. Invoices and ledger entries must already be saved in DB for this session.
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

    inv_by_id = {r.id: r for r in inv_rows}
    led_by_id = {r.id: r for r in led_rows}

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
    kept_ledger_ids = {e["_db_id"] for e in filtered_ledger}
    for entry in ledger:
        if entry["_db_id"] not in kept_ledger_ids:
            skipped_items.append(SkippedSchema(
                item_type="ledger_entry",
                item_ref=entry.get("reference"),
                reason=f"Date too far from any invoice date (±{CANDIDATE_WINDOW_DAYS} day window)",
                detail={"date": entry.get("date") or ""},
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
        inv_orm  = inv_by_id[inv_dict["_db_id"]]
        led_orm  = led_by_id[led_dict["_db_id"]]

        breakdown_raw = compute_field_breakdown(inv_dict, led_dict)
        status_str    = result["status"]

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

        matched_pairs.append(MatchedPair(
            match_id        = match_db.id,
            invoice         = _invoice_schema(inv_orm),
            ledger_entry    = _ledger_schema(led_orm),
            score           = result["score"],
            status          = status_str,
            field_breakdown = _breakdown_schema(breakdown_raw),
        ))

    # Invoices the optimiser could not assign at all (more invoices than
    # candidate ledger entries) — report them instead of silently dropping.
    assigned_invoice_idx = {r["invoice_idx"] for r in classified}
    for idx, inv_dict in enumerate(filtered_invoices):
        if idx not in assigned_invoice_idx:
            skipped_items.append(SkippedSchema(
                item_type="invoice",
                item_ref=inv_dict.get("invoice_number"),
                reason="No ledger entry left to pair with (more invoices than candidate ledger entries)",
                detail={"vendor": inv_dict.get("vendor_name") or "", "amount": inv_dict.get("amount") or ""},
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

    summary = build_summary(matched_pairs, len(inv_rows), len(led_rows), len(skipped_items))
    logger.info(
        "[%s] Matching done. auto=%d review=%d unmatched=%d skipped=%d",
        session_id, summary.auto_match_count, summary.review_count,
        summary.unmatched_count, summary.skipped_count,
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
        .order_by(MatchResultDB.created_at)
    )).scalars().all()

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

        matched_pairs.append(MatchedPair(
            match_id        = mr.id,
            invoice         = _invoice_schema(inv_orm),
            ledger_entry    = _ledger_schema(led_orm),
            score           = mr.score,
            status          = mr.override_status or mr.status.value,
            field_breakdown = _breakdown_schema(mr.field_breakdown or {}),
            is_overridden   = bool(mr.is_overridden),
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

    return MatchResponse(
        session_id = session_id,
        summary    = build_summary(matched_pairs, len(inv_rows), len(led_rows), len(skipped)),
        matches    = matched_pairs,
        skipped    = skipped,
        created_at = session_row.created_at,
    )


def build_summary(
    pairs: list[MatchedPair],
    total_invoices: int,
    total_ledger: int,
    skipped_count: int,
) -> MatchSummary:
    """Count pairs per effective status (a human override wins over the automatic one)."""
    counts: dict[str, int] = {}
    for p in pairs:
        effective = p.override_status or p.status
        counts[effective] = counts.get(effective, 0) + 1

    return MatchSummary(
        total_invoices   = total_invoices,
        total_ledger     = total_ledger,
        auto_match_count = counts.get("auto_match", 0),
        review_count     = counts.get("review", 0),
        unmatched_count  = counts.get("unmatched", 0),
        confirmed_count  = counts.get("confirmed", 0),
        rejected_count   = counts.get("rejected", 0),
        skipped_count    = skipped_count,
    )


# ORM → schema helpers
def _invoice_schema(r: Invoice) -> ExtractedInvoice:
    return ExtractedInvoice(
        id=r.id, source_file=r.source_file,
        invoice_number=r.invoice_number, vendor_name=r.vendor_name,
        date=r.date, amount=r.amount,
        parsed_date=r.parsed_date, parsed_amount=r.parsed_amount,
    )


def _ledger_schema(r: LedgerEntry) -> ExtractedLedgerEntry:
    return ExtractedLedgerEntry(
        id=r.id, source_file=r.source_file,
        reference=r.reference, vendor=r.vendor,
        date=r.date, debit=r.debit, credit=r.credit,
        parsed_date=r.parsed_date,
        debit_amount=r.debit_amount, credit_amount=r.credit_amount,
    )


def _breakdown_schema(raw: dict) -> FieldBreakdown:
    def _field(name: str) -> FieldScore:
        default = {"score": 0, "weight": WEIGHTS[name], "contribution": 0,
                   "invoice_value": "", "ledger_value": ""}
        return FieldScore(**raw.get(name, default))

    return FieldBreakdown(
        invoice_number=_field("invoice_number"),
        vendor=_field("vendor"),
        date=_field("date"),
        amount=_field("amount"),
    )


# ORM → dict helpers
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
