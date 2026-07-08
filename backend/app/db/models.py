from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Text,
    ForeignKey, Boolean, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
import uuid
import enum

Base = declarative_base()


def _uuid():
    return str(uuid.uuid4())


class MatchStatus(str, enum.Enum):
    auto_match = "auto_match"
    review     = "review"
    unmatched  = "unmatched"


class UploadSession(Base):
    """
    Groups an invoice upload + ledger upload into one session.
    Stores the final match run result for cache/retrieval.
    """
    __tablename__ = "upload_sessions"

    id              = Column(String, primary_key=True, default=_uuid)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    invoice_files   = Column(JSON, nullable=True)   # list of original filenames
    ledger_files    = Column(JSON, nullable=True)
    status          = Column(String, default="pending")  # pending | processing | done | error
    error_message   = Column(Text, nullable=True)

    invoices        = relationship("Invoice",      back_populates="session", cascade="all, delete-orphan")
    ledger_entries  = relationship("LedgerEntry",  back_populates="session", cascade="all, delete-orphan")
    match_results   = relationship("MatchResultDB", back_populates="session", cascade="all, delete-orphan")
    skipped_items   = relationship("SkippedItem",  back_populates="session", cascade="all, delete-orphan")


class Invoice(Base):
    """One extracted invoice."""
    __tablename__ = "invoices"

    id                  = Column(String, primary_key=True, default=_uuid)
    session_id          = Column(String, ForeignKey("upload_sessions.id"), nullable=False)
    source_file         = Column(String, nullable=True)    # original filename
    invoice_number      = Column(String, nullable=True)
    vendor_name         = Column(String, nullable=True)
    date                = Column(String, nullable=True)    # raw string
    amount              = Column(String, nullable=True)    # raw string
    parsed_date         = Column(DateTime, nullable=True)
    parsed_amount       = Column(Float, nullable=True)
    normalized_invoice_number = Column(String, nullable=True)
    normalized_vendor   = Column(String, nullable=True)
    raw_text            = Column(Text, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow)

    session             = relationship("UploadSession", back_populates="invoices")
    match_result        = relationship("MatchResultDB", back_populates="invoice", uselist=False)


class LedgerEntry(Base):
    """One extracted ledger row."""
    __tablename__ = "ledger_entries"

    id                  = Column(String, primary_key=True, default=_uuid)
    session_id          = Column(String, ForeignKey("upload_sessions.id"), nullable=False)
    source_file         = Column(String, nullable=True)
    reference           = Column(String, nullable=True)
    vendor              = Column(String, nullable=True)
    date                = Column(String, nullable=True)
    debit               = Column(String, nullable=True)
    credit              = Column(String, nullable=True)
    parsed_date         = Column(DateTime, nullable=True)
    debit_amount        = Column(Float, nullable=True)
    credit_amount       = Column(Float, nullable=True)
    normalized_reference = Column(String, nullable=True)
    normalized_vendor   = Column(String, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow)

    session             = relationship("UploadSession", back_populates="ledger_entries")
    match_result        = relationship("MatchResultDB", back_populates="ledger_entry", uselist=False)


class MatchResultDB(Base):
    """
    One matched pair: invoice ↔ ledger entry.
    Stores full explainability breakdown as JSON.
    """
    __tablename__ = "match_results"

    id              = Column(String, primary_key=True, default=_uuid)
    session_id      = Column(String, ForeignKey("upload_sessions.id"), nullable=False)
    invoice_id      = Column(String, ForeignKey("invoices.id"), nullable=False)
    ledger_entry_id = Column(String, ForeignKey("ledger_entries.id"), nullable=False)

    score           = Column(Float, nullable=False)
    status          = Column(SAEnum(MatchStatus), nullable=False)

    # field-level breakdown for explainability
    field_breakdown = Column(JSON, nullable=True)

    # human override
    is_overridden   = Column(Boolean, default=False)
    override_status = Column(String, nullable=True)
    override_note   = Column(Text, nullable=True)
    overridden_at   = Column(DateTime, nullable=True)

    created_at      = Column(DateTime, default=datetime.utcnow)

    session         = relationship("UploadSession",  back_populates="match_results")
    invoice         = relationship("Invoice",        back_populates="match_result")
    ledger_entry    = relationship("LedgerEntry",    back_populates="match_result")


class SkippedItem(Base):
    """
    Records invoices or ledger entries that were filtered out
    before matching, with the reason why.
    """
    __tablename__ = "skipped_items"

    id          = Column(String, primary_key=True, default=_uuid)
    session_id  = Column(String, ForeignKey("upload_sessions.id"), nullable=False)
    item_type   = Column(String, nullable=False)   # "invoice" | "ledger_entry"
    item_ref    = Column(String, nullable=True)    # invoice number or ledger reference
    reason      = Column(String, nullable=False)   # human-readable reason
    detail      = Column(JSON, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    session     = relationship("UploadSession", back_populates="skipped_items")
