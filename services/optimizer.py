"""
services/optimizer.py
----------------------
Enforce one-to-one matching between invoices and ledger entries
using the Hungarian algorithm (scipy.optimize.linear_sum_assignment).

Why Hungarian instead of greedy?
  • Greedy picks the highest score for each invoice independently,
    which can assign two invoices to the same ledger entry.
  • Hungarian finds the globally optimal assignment that maximises
    the total similarity — no duplicates.

Core idea:
  score_matrix[i][j]  → similarity(invoice_i, ledger_j)
  cost_matrix[i][j]   = 1 - score_matrix[i][j]   (Hungarian minimises cost)
  linear_sum_assignment(cost_matrix) → optimal row_indices, col_indices
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from scipy.optimize import linear_sum_assignment  # type: ignore

from utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class MatchResult(NamedTuple):
    invoice_idx: int    # index into the invoices list
    ledger_idx:  int    # index into the ledger_entries list
    score:       float  # similarity score ∈ [0, 1]


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def optimize_matches(score_matrix: np.ndarray) -> list[MatchResult]:
    """
    Apply the Hungarian algorithm to find the globally optimal one-to-one
    assignment of invoices to ledger entries.

    Parameters
    ----------
    score_matrix : np.ndarray of shape (n_invoices, n_ledger)
        Each cell score_matrix[i][j] is the similarity of invoice i to ledger j.

    Returns
    -------
    list[MatchResult]
        One MatchResult per invoice (row), sorted by invoice index.
        If there are fewer ledger entries than invoices, some invoices will be
        matched to their best available candidate (the algorithm handles this).
    """
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

    # linear_sum_assignment handles non-square matrices:
    # if n_invoices > n_ledger, some ledger entries are shared
    # (which we accept as a limitation when ledger is smaller than invoices).
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


# ---------------------------------------------------------------------------
# Candidate filtering (optional pre-step to reduce matrix size)
# ---------------------------------------------------------------------------

def filter_candidates(
    invoices: list[dict],
    ledger_entries: list[dict],
    max_days: int = 60,
) -> tuple[list[dict], list[dict]]:
    """
    Optional pre-filter: discard ledger entries that are more than `max_days`
    away from every invoice date.  Reduces matrix size for large datasets.

    Returns a (possibly smaller) pair of (invoices, ledger_entries).
    Both original lists are returned unchanged if dates are unavailable.
    """
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
