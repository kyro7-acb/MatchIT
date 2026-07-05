"""
backend/app/models/schemas.py
------------------------------
Pydantic models for all API request/response payloads.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Upload responses
# ---------------------------------------------------------------------------

class ExtractedInvoice(BaseModel):
    id:             str
    source_file:    Optional[str]
    invoice_number: Optional[str]
    vendor_name:    Optional[str]
    date:           Optional[str]
    amount:         Optional[str]
    parsed_date:    Optional[datetime]
    parsed_amount:  Optional[float]


class ExtractedLedgerEntry(BaseModel):
    id:        str
    source_file: Optional[str]
    reference: Optional[str]
    vendor:    Optional[str]
    date:      Optional[str]
    debit:     Optional[str]
    credit:    Optional[str]
    parsed_date:    Optional[datetime]
    debit_amount:   Optional[float]
    credit_amount:  Optional[float]


class UploadResponse(BaseModel):
    session_id: str
    message:    str
    count:      int
    items:      List[ExtractedInvoice | ExtractedLedgerEntry]


# ---------------------------------------------------------------------------
# Field breakdown (explainability)
# ---------------------------------------------------------------------------

class FieldScore(BaseModel):
    score:          float
    weight:         float
    contribution:   float
    invoice_value:  Optional[str] = ""
    ledger_value:   Optional[str] = ""


class FieldBreakdown(BaseModel):
    invoice_number: FieldScore
    vendor:         FieldScore
    date:           FieldScore
    amount:         FieldScore


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------

class MatchedPair(BaseModel):
    match_id:       str
    invoice:        ExtractedInvoice
    ledger_entry:   ExtractedLedgerEntry
    score:          float
    status:         str            # auto_match | review | unmatched
    field_breakdown: FieldBreakdown
    is_overridden:  bool = False
    override_status: Optional[str] = None
    override_note:   Optional[str] = None


class SkippedItem(BaseModel):
    item_type:  str    # "invoice" | "ledger_entry"
    item_ref:   Optional[str]
    reason:     str
    detail:     Optional[Dict[str, Any]]


class MatchSummary(BaseModel):
    total_invoices:     int
    total_ledger:       int
    auto_match_count:   int
    review_count:       int
    unmatched_count:    int
    skipped_count:      int


class MatchResponse(BaseModel):
    session_id: str
    summary:    MatchSummary
    matches:    List[MatchedPair]
    skipped:    List[SkippedItem]
    created_at: datetime


# ---------------------------------------------------------------------------
# Override request
# ---------------------------------------------------------------------------

class OverrideRequest(BaseModel):
    status: str = Field(..., pattern="^(auto_match|review|unmatched|confirmed|rejected)$")
    note:   Optional[str] = None


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------

class SessionSummary(BaseModel):
    session_id:     str
    created_at:     datetime
    status:         str
    invoice_files:  Optional[List[str]]
    ledger_files:   Optional[List[str]]
    match_summary:  Optional[MatchSummary]
