import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.utils import get_logger
from app.db.session import get_db
from app.db.models import UploadSession, MatchResultDB, MatchStatus
from app.models.schemas import MatchResponse, OverrideRequest, SessionSummary, MatchSummary
from app.services.matching_service import run_full_pipeline, get_cached_result

router = APIRouter()
logger = get_logger(__name__)

# POST /api/match
@router.post("/match", response_model=MatchResponse)
async def run_match(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Run the full matching pipeline for a session. Returns cached result if already computed.
    """
    # Check cache first
    cached = await get_cached_result(session_id, db)
    if cached:
        logger.info("Returning cached result for session %s", session_id)
        return cached

    session_row = await db.get(UploadSession, session_id)
    if not session_row:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    try:
        result = await run_full_pipeline(session_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Pipeline error for session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=f"Matching pipeline error: {e}")

# GET /api/match/{session_id}
@router.get("/match/{session_id}", response_model=MatchResponse)
async def get_match_result(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve previously computed matching results."""
    result = await get_cached_result(session_id, db)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No completed results for session '{session_id}'. Run POST /api/match first."
        )
    return result


# POST /api/match/{match_id}/override
@router.post("/match/{match_id}/override")
async def override_match(
    match_id: str,
    body:     OverrideRequest,
    db:       AsyncSession = Depends(get_db),
):
    """
    Manually override the status of a match result. Records who changed it and when.
    """
    mr = await db.get(MatchResultDB, match_id)
    if not mr:
        raise HTTPException(status_code=404, detail=f"Match '{match_id}' not found.")

    mr.is_overridden   = True
    mr.override_status = body.status
    mr.override_note   = body.note
    mr.overridden_at   = datetime.utcnow()

    await db.flush()
    logger.info("Match %s overridden to '%s'", match_id, body.status)

    return {"message": f"Match '{match_id}' overridden to '{body.status}'.", "match_id": match_id}

# GET /api/sessions
@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List past upload sessions with basic summary."""
    rows = (await db.execute(
        select(UploadSession)
        .order_by(desc(UploadSession.created_at))
        .limit(limit)
        .offset(offset)
    )).scalars().all()

    summaries: list[SessionSummary] = []
    for row in rows:
        match_rows = (await db.execute(
            select(MatchResultDB).where(MatchResultDB.session_id == row.id)
        )).scalars().all()

        ms = None
        if match_rows:
            auto = sum(1 for m in match_rows if (m.override_status or m.status.value) == "auto_match")
            rev  = sum(1 for m in match_rows if (m.override_status or m.status.value) == "review")
            unm  = sum(1 for m in match_rows if (m.override_status or m.status.value) == "unmatched")
            ms   = MatchSummary(
                total_invoices=0, total_ledger=0,
                auto_match_count=auto, review_count=rev,
                unmatched_count=unm, skipped_count=0,
            )

        summaries.append(SessionSummary(
            session_id    = row.id,
            created_at    = row.created_at,
            status        = row.status,
            invoice_files = row.invoice_files,
            ledger_files  = row.ledger_files,
            match_summary = ms,
        ))

    return summaries

# GET /api/match/{session_id}/export
@router.get("/match/{session_id}/export")
async def export_results(
    session_id: str,
    fmt: str = Query("json", pattern="^(json|csv)$"),
    db:  AsyncSession = Depends(get_db),
):
    """Download matching results as JSON or CSV."""
    result = await get_cached_result(session_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="No results found for this session.")

    if fmt == "json":
        content = result.model_dump_json(indent=2)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=matchIT_{session_id}.json"},
        )

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "match_id", "invoice_number", "invoice_vendor", "invoice_date", "invoice_amount",
        "ledger_ref", "ledger_vendor", "ledger_date", "ledger_debit",
        "score", "status",
        "inv_no_score", "vendor_score", "date_score", "amount_score",
        "is_overridden", "override_status", "override_note",
    ])
    for m in result.matches:
        bd = m.field_breakdown
        writer.writerow([
            m.match_id,
            m.invoice.invoice_number, m.invoice.vendor_name,
            m.invoice.date, m.invoice.amount,
            m.ledger_entry.reference, m.ledger_entry.vendor,
            m.ledger_entry.date, m.ledger_entry.debit,
            m.score, m.status,
            bd.invoice_number.score, bd.vendor.score, bd.date.score, bd.amount.score,
            m.is_overridden, m.override_status or "", m.override_note or "",
        ])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=matchIT_{session_id}.csv"},
    )
