from __future__ import annotations

from typing import NamedTuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.core.utils import get_logger

logger = get_logger(__name__)


class MatchResult(NamedTuple):
    invoice_idx: int    # index into the invoices list
    ledger_idx:  int    # index into the ledger_entries list
    score:       float  # similarity score ∈ [0, 1]


# Optimizer
def optimize_matches(score_matrix: np.ndarray) -> list[MatchResult]:

    if score_matrix.size == 0:
        logger.warning("Empty score matrix — no matches to compute.")
        return []

    n_invoices, n_ledger = score_matrix.shape
    logger.info(
        "Running Hungarian algorithm on %d×%d score matrix.",
        n_invoices, n_ledger,
    )

    # Hungarian minimises cost → convert similarity → cost
    cost_matrix = 1.0 - score_matrix

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matches: list[MatchResult] = []
    for invoice_idx, ledger_idx in zip(row_ind, col_ind):
        score = float(score_matrix[invoice_idx, ledger_idx])
        matches.append(MatchResult(
            invoice_idx=int(invoice_idx),
            ledger_idx=int(ledger_idx),
            score=score,
        ))
        logger.debug(
            "Matched invoice[%d] ↔ ledger[%d]  score=%.4f",
            invoice_idx, ledger_idx, score,
        )

    # Sort by invoice index for deterministic output
    matches.sort(key=lambda m: m.invoice_idx)
    logger.info("Hungarian algorithm produced %d matches.", len(matches))
    return matches


# Candidate filtering (optional pre-step to reduce matrix size)
def filter_candidates(
    invoices: list[dict],
    ledger_entries: list[dict],
    max_days: int = 60,
) -> tuple[list[dict], list[dict]]:

    # Only filter when at least one invoice has a parsed date
    invoice_dates = [
        inv["parsed_date"] for inv in invoices
        if inv.get("parsed_date") is not None
    ]
    if not invoice_dates:
        return invoices, ledger_entries

    filtered: list[dict] = []
    for entry in ledger_entries:
        entry_date = entry.get("parsed_date")
        if entry_date is None:
            filtered.append(entry)   # keep if no date (conservative)
            continue
        for inv_date in invoice_dates:
            if abs((entry_date - inv_date).days) <= max_days:
                filtered.append(entry)
                break

    removed = len(ledger_entries) - len(filtered)
    if removed:
        logger.info(
            "Candidate filtering removed %d ledger entries (date window ±%d days).",
            removed, max_days,
        )
    return invoices, filtered
