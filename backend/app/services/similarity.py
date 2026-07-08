from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import numpy as np

from app.core.config import AMOUNT_TOLERANCE_PERCENT, DATE_TOLERANCE_DAYS, WEIGHTS
from app.core.utils import get_logger

logger = get_logger(__name__)

# Levenshtein similarity
def levenshtein_distance(s1: str, s2: str) -> int:

    m, n = len(s1), len(s2)
    # dp[i][j] = edit distance between s1[:i] and s2[:j]
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i          # cost of deleting all chars in s1[:i]
    for j in range(n + 1):
        dp[0][j] = j          # cost of inserting all chars of s2[:j]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]   # no edit needed
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],     # deletion
                    dp[i][j - 1],     # insertion
                    dp[i - 1][j - 1], # substitution
                )

    return dp[m][n]


def levenshtein_similarity(s1: str, s2: str) -> float:

    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    dist = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - dist / max_len

# Jaro-Winkler similarity
def jaro_similarity(s1: str, s2: str) -> float:

    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    match_distance = max(len(s1), len(s2)) // 2 - 1
    match_distance = max(match_distance, 0)

    s1_matches = [False] * len(s1)
    s2_matches = [False] * len(s2)

    matches = 0
    transpositions = 0

    # Count matches
    for i, ch1 in enumerate(s1):
        start = max(0, i - match_distance)
        end   = min(i + match_distance + 1, len(s2))
        for j in range(start, end):
            if s2_matches[j] or ch1 != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    # Count transpositions
    k = 0
    for i, matched in enumerate(s1_matches):
        if not matched:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (
        matches / len(s1) +
        matches / len(s2) +
        (matches - transpositions / 2) / matches
    ) / 3.0
    return jaro


def jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:

    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    jaro = jaro_similarity(s1, s2)

    # Common prefix length (max 4)
    prefix_len = 0
    for c1, c2 in zip(s1[:4], s2[:4]):
        if c1 == c2:
            prefix_len += 1
        else:
            break

    return jaro + prefix_len * p * (1 - jaro)


# Date similarity
def date_similarity(d1: Optional[datetime], d2: Optional[datetime]) -> float:

    if d1 is None and d2 is None:
        return 0.5
    if d1 is None or d2 is None:
        return 0.0

    diff_days = abs((d1 - d2).days)
    if diff_days == 0:
        return 1.0
    if diff_days <= DATE_TOLERANCE_DAYS:
        # Linear decay: 1 day → ~0.83 (for tolerance=3)
        return 1.0 - (diff_days / (DATE_TOLERANCE_DAYS * 2))
    return 0.0


# Amount similarity
def amount_similarity(
    a1: Optional[float],
    a2: Optional[float],
) -> float:
       
    if a1 is None and a2 is None:
        return 0.5
    if a1 is None or a2 is None:
        return 0.0
    if a1 == 0 and a2 == 0:
        return 1.0
    if a1 == 0 or a2 == 0:
        return 0.0

    relative_error = abs(a1 - a2) / max(abs(a1), abs(a2))

    if relative_error <= AMOUNT_TOLERANCE_PERCENT:
        return 1.0

    # Exponential decay — score drops quickly for large errors
    return math.exp(-10 * relative_error)


# Composite similarity score
def compute_similarity(invoice: dict, ledger: dict) -> float:
    
    s_invoice = levenshtein_similarity(
        invoice.get("normalized_invoice_number", ""),
        ledger.get("normalized_reference", ""),
    )

    s_vendor = jaro_winkler(
        invoice.get("normalized_vendor", ""),
        ledger.get("normalized_vendor", ""),
    )

    s_date = date_similarity(
        invoice.get("parsed_date"),
        ledger.get("parsed_date"),
    )

    # Use debit_amount as primary; fall back to credit_amount
    ledger_amount = ledger.get("debit_amount") or ledger.get("credit_amount")
    s_amount = amount_similarity(
        invoice.get("parsed_amount"),
        ledger_amount,
    )

    w = WEIGHTS
    final_score = (
        w["invoice_number"] * s_invoice +
        w["vendor"]         * s_vendor  +
        w["date"]           * s_date    +
        w["amount"]         * s_amount
    )

    logger.debug(
        "Similarity: inv=%s ref=%s → s_inv=%.3f s_ven=%.3f s_date=%.3f s_amt=%.3f → final=%.4f",
        invoice.get("normalized_invoice_number"),
        ledger.get("normalized_reference"),
        s_invoice, s_vendor, s_date, s_amount, final_score,
    )

    return final_score

# Score matrix builder
def build_score_matrix(invoices: list[dict], ledger_entries: list[dict]) -> np.ndarray:
    """
    Build an (n_invoices × n_ledger) numpy array of similarity scores. This matrix is fed directly into optimizer.py.
    """
    n = len(invoices)
    m = len(ledger_entries)
    matrix = np.zeros((n, m), dtype=float)

    for i, invoice in enumerate(invoices):
        for j, ledger in enumerate(ledger_entries):
            matrix[i, j] = compute_similarity(invoice, ledger)

    logger.info("Score matrix built: shape=%dx%d", n, m)
    return matrix
