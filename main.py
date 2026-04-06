"""
main.py
--------
Full Invoice-to-Ledger Matching Engine pipeline.

Usage
-----
# With a real invoice image + ledger JSON:
python main.py --image path/to/invoice.jpg --ledger path/to/ledger.json

# With multiple invoice images:
python main.py --image inv1.jpg inv2.jpg --ledger ledger.json

# Using bundled mock data (no real image required):
python main.py --mock

# Verbose logging:
python main.py --mock --log-level DEBUG
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from services.preprocess import preprocess_invoices, preprocess_ledger
from services.similarity import build_score_matrix
from services.optimizer import optimize_matches, filter_candidates
from services.classifier import classify_matches
from utils import get_logger, print_match_table

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Mock data (used when --mock flag is passed)
# ---------------------------------------------------------------------------

MOCK_INVOICES = [
    {
        "invoice_number": "INV-2024-001",
        "vendor_name":    "Himalayan Traders Pvt Ltd",
        "date":           "15/01/2024",
        "amount":         "45000.00",
    },
    {
        "invoice_number": "INV-2024-002",
        "vendor_name":    "Kathmandu Supplies Co",
        "date":           "20/01/2024",
        "amount":         "12500.50",
    },
    {
        "invoice_number": "INV-2024-003",
        "vendor_name":    "Nepal Electronics Ltd",
        "date":           "22/01/2024",
        "amount":         "7800.00",
    },
    {
        "invoice_number": "INV-2024-004",
        "vendor_name":    "Everest Goods Inc",
        "date":           "25/01/2024",
        "amount":         "33200.00",
    },
]

MOCK_LEDGER = [
    {
        "reference": "INV-2024-001",
        "vendor":    "Himalayan Traders Pvt Ltd",
        "date":      "15/01/2024",
        "debit":     "45000.00",
        "credit":    None,
    },
    {
        "reference": "INV2024002",          # slightly different format
        "vendor":    "Ktm Supplies Company",
        "date":      "21/01/2024",          # 1 day off
        "debit":     "12500.50",
        "credit":    None,
    },
    {
        "reference": "INV-2024-003",
        "vendor":    "Nepal Electronics",
        "date":      "22/01/2024",
        "debit":     "7750.00",             # slightly different amount
        "credit":    None,
    },
    {
        "reference": "REF-9999",            # no close match → unmatched
        "vendor":    "Random Vendor",
        "date":      "01/06/2024",
        "debit":     "1.00",
        "credit":    None,
    },
]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline_from_images(
    image_paths: list[str],
    ledger_data: list[dict],
) -> list[dict]:
    """
    Full pipeline: image files → classified match results.

    1. Extract structured data from each invoice image via OCR.
    2. Preprocess invoices + ledger.
    3. Filter candidates.
    4. Build score matrix.
    5. Run Hungarian algorithm.
    6. Classify results.
    """
    # Import extract here so that PaddleOCR is only loaded when images are provided
    from services.extract import extract_invoice

    raw_invoices: list[dict] = []
    for path in image_paths:
        logger.info("Extracting invoice from: %s", path)
        try:
            inv = extract_invoice(path)
            inv["_source_image"] = path
            raw_invoices.append(inv)
        except FileNotFoundError as e:
            logger.error("%s — skipping.", e)
        except Exception as e:
            logger.error("Extraction failed for %s: %s", path, e)

    if not raw_invoices:
        logger.error("No invoices could be extracted. Aborting.")
        sys.exit(1)

    return _run_matching(raw_invoices, ledger_data)


def run_pipeline_from_mock(
    mock_invoices: list[dict] | None = None,
    mock_ledger: list[dict] | None = None,
) -> list[dict]:
    """Pipeline using pre-structured (mock) data — no OCR required."""
    invoices = mock_invoices or MOCK_INVOICES
    ledger   = mock_ledger   or MOCK_LEDGER
    return _run_matching(invoices, ledger)


def _run_matching(raw_invoices: list[dict], raw_ledger: list[dict]) -> list[dict]:
    """
    Shared core matching logic (used by both image and mock pipelines).
    """
    logger.info("Step 1/5 — Preprocessing %d invoices …", len(raw_invoices))
    invoices = preprocess_invoices(raw_invoices)

    logger.info("Step 2/5 — Preprocessing %d ledger entries …", len(raw_ledger))
    ledger   = preprocess_ledger(raw_ledger)

    logger.info("Step 3/5 — Filtering candidates …")
    invoices, ledger = filter_candidates(invoices, ledger)

    logger.info("Step 4/5 — Building score matrix …")
    score_matrix = build_score_matrix(invoices, ledger)

    logger.info("Step 5/5 — Running Hungarian optimiser …")
    matches  = optimize_matches(score_matrix)

    logger.info("Classifying %d matches …", len(matches))
    results  = classify_matches(matches, invoices, ledger)

    return results


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def output_results(results: list[dict], output_json: str | None = None) -> None:
    """Print a console table and optionally write JSON output."""
    print("\n" + "=" * 60)
    print(" INVOICE ↔ LEDGER MATCHING RESULTS")
    print("=" * 60)
    print_match_table(results)

    print("\nDetailed JSON output:")
    # Strip internal detail for cleaner top-level display
    summary = [
        {k: v for k, v in r.items() if k not in ("invoice_idx", "ledger_idx")}
        for r in results
    ]
    print(json.dumps(summary, indent=2, default=str))

    if output_json:
        Path(output_json).write_text(json.dumps(results, indent=2, default=str))
        logger.info("Full results written to: %s", output_json)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Invoice-to-Ledger Matching Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--image", nargs="+", metavar="PATH",
        help="One or more invoice image paths to extract and match.",
    )
    mode.add_argument(
        "--mock", action="store_true",
        help="Run with built-in mock data (no images required).",
    )
    parser.add_argument(
        "--ledger", metavar="PATH",
        help="Path to a JSON file containing ledger entries (required with --image).",
    )
    parser.add_argument(
        "--output", metavar="PATH",
        help="Write full JSON results to this file.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    # Apply log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    if args.mock:
        logger.info("Running in MOCK mode …")
        results = run_pipeline_from_mock()
    else:
        if not args.ledger:
            parser.error("--ledger is required when using --image.")
        ledger_path = Path(args.ledger)
        if not ledger_path.exists():
            logger.error("Ledger file not found: %s", ledger_path)
            sys.exit(1)
        raw_ledger = json.loads(ledger_path.read_text())
        results = run_pipeline_from_images(args.image, raw_ledger)

    output_results(results, output_json=args.output)


if __name__ == "__main__":
    main()
