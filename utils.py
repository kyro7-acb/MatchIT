import logging

from config import LOG_LEVEL


# Logging setup
def get_logger(name: str) -> logging.Logger:
    """Return a consistently-configured logger."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=level,
    )
    return logging.getLogger(name)


# Console table printer
def print_match_table(results: list[dict]) -> None:
    if not results:
        print("No results to display.")
        return

    headers = ["Invoice ID", "Ledger Ref", "Score", "Status"]
    col_widths = [max(len(h), 12) for h in headers]

    # Adjust widths based on data
    for r in results:
        col_widths[0] = max(col_widths[0], len(str(r.get("invoice_id", ""))))
        col_widths[1] = max(col_widths[1], len(str(r.get("ledger_ref", ""))))
        col_widths[2] = max(col_widths[2], 6)
        col_widths[3] = max(col_widths[3], len(str(r.get("status", ""))))

    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"

    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for r in results:
        score_str = f"{r.get('score', 0):.4f}"
        print(fmt.format(
            str(r.get("invoice_id", "N/A")),
            str(r.get("ledger_ref", "N/A")),
            score_str,
            str(r.get("status", "N/A")),
        ))
    print(sep)
