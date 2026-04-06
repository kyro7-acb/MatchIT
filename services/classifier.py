"""
services/classifier.py
-----------------------
Interpret similarity scores and assign a human-readable status label.

Labels:
  • auto_match  — high confidence; can be applied without human review
  • review      — moderate confidence; a human should verify
  • unmatched   — low confidence; no reliable match found

Thresholds are defined in config.py and can be tuned without code changes.
"""

from __future__ import annotations

from config import THRESHOLDS
from services.optimizer import MatchResult
from utils import get_logger

logger = get_logger(__name__)

# Type alias for a classified result
ClassifiedMatch = dict  # keys: invoice_idx, ledger_idx, score, status


def classify(score: float) -> str:
    """
    Map a similarity score to a status label.

    Parameters
    ----------
    score : float ∈ [0, 1]

    Returns
    -------
    str — one of 'auto_match', 'review', 'unmatched'
    """
    if score >= THRESHOLDS["auto_match"]:
        return "auto_match"
    elif score >= THRESHOLDS["review"]:
        return "review"
    else:
        return "unmatched"


def classify_matches(
    matches: list[MatchResult],
    invoices: list[dict],
    ledger_entries: list[dict],
) -> list[ClassifiedMatch]:
    """
    Enrich each MatchResult with:
      • status label (auto_match / review / unmatched)
      • human-readable invoice ID  (invoice_number or index)
      • human-readable ledger reference

    Parameters
    ----------
    matches        : output of optimizer.optimize_matches()
    invoices       : preprocessed invoice dicts
    ledger_entries : preprocessed ledger entry dicts

    Returns
    -------
    list of dicts ready for JSON serialisation or console display
    """
    results: list[ClassifiedMatch] = []

    for match in matches:
        inv  = invoices[match.invoice_idx]
        led  = ledger_entries[match.ledger_idx]

        status = classify(match.score)

        classified: ClassifiedMatch = {
            "invoice_idx":  match.invoice_idx,
            "ledger_idx":   match.ledger_idx,
            "invoice_id":   inv.get("invoice_number") or f"inv_{match.invoice_idx}",
            "ledger_ref":   led.get("reference")      or f"led_{match.ledger_idx}",
            "score":        round(match.score, 6),
            "status":       status,
            # Attach key normalised fields for auditability
            "detail": {
                "invoice_number_norm": inv.get("normalized_invoice_number"),
                "ledger_ref_norm":     led.get("normalized_reference"),
                "invoice_vendor":      inv.get("normalized_vendor"),
                "ledger_vendor":       led.get("normalized_vendor"),
                "invoice_date":        str(inv.get("parsed_date", "")),
                "ledger_date":         str(led.get("parsed_date", "")),
                "invoice_amount":      inv.get("parsed_amount"),
                "ledger_debit":        led.get("debit_amount"),
            },
        }

        logger.debug(
            "classify: %s ↔ %s  score=%.4f  status=%s",
            classified["invoice_id"],
            classified["ledger_ref"],
            match.score,
            status,
        )

        results.append(classified)

    # Log summary
    counts = {"auto_match": 0, "review": 0, "unmatched": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    logger.info(
        "Classification summary: auto_match=%d  review=%d  unmatched=%d",
        counts["auto_match"], counts["review"], counts["unmatched"],
    )

    return results
