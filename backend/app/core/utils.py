import logging
import re
from datetime import datetime
from typing import Optional

from app.core.config import LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=LOG_LEVEL,
    )
    return logging.getLogger(name)


logger = get_logger(__name__)


# Date parsing
_DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
    "%d.%m.%Y", "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S",
    "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
    "%b %d %Y",  "%B %d %Y",
    "%d/%m/%y",  "%m/%d/%y",
    "%d-%b-%Y", "%d-%B-%Y", "%d-%b-%y", "%d-%B-%y",
    "%d.%b.%Y", "%d.%B.%Y",
]


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string against the known formats (day-first wins on
    ambiguous dd/mm vs mm/dd input).

    Dates more than a year in the future are rejected: they are almost
    always Bikram Sambat (Nepali calendar) dates such as "2082-10-15" that
    happen to fit a Gregorian format, and comparing them against Gregorian
    dates would produce meaningless scores.
    """
    if not date_str:
        return None
    cleaned = re.sub(r"\s+", " ", str(date_str).strip().rstrip(","))
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

        if parsed.year > datetime.now().year + 1:
            logger.warning(
                "parse_date: %r parsed to implausible year %d (likely a "
                "non-Gregorian calendar date) — treating as unparseable.",
                date_str, parsed.year,
            )
            return None

        return parsed
    logger.debug("parse_date: could not parse date string %r with any known format.", date_str)
    return None


# Amount parsing
_AMOUNT_RE = re.compile(r"\d[\d,]*(?:\.\d+)?|\.\d+")


def parse_amount(amount_str: Optional[str]) -> Optional[float]:
    """
    Extract the numeric value from an amount string such as "45,000.00",
    "Rs. 12,500.50" or "NPR 1,23,456". Currency symbols, prefixes and
    thousands separators are ignored; the first number found is used.
    """
    if amount_str is None or amount_str == "":
        return None
    m = _AMOUNT_RE.search(str(amount_str))
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None
