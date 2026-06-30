"""Field normalization rules (§11). Pure functions, fully unit-tested."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional


_CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "MAD": "MAD"}


def normalize_amount(raw: Optional[str]) -> Optional[float]:
    """Normalize `1 234,56`, `1,234.56`, `1234.56`, `1234,56` -> float."""
    if raw is None:
        return None
    s = str(raw).strip().replace("\xa0", "").replace(" ", "")
    if not s:
        return None
    # Strip currency symbols
    s = re.sub(r"[€$£]", "", s)
    has_comma = "," in s
    has_dot = "." in s
    if has_comma and has_dot:
        # last separator is the decimal one
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma and not has_dot:
        s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """Return ISO YYYY-MM-DD or None."""
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_currency(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip().upper()
    if s in _CURRENCY_SYMBOLS.values() or s in ("MAD",):
        return s
    if s in _CURRENCY_SYMBOLS:
        return _CURRENCY_SYMBOLS[s]
    return None


def normalize_vat(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return re.sub(r"\s+", "", str(raw)).upper()


def normalize_supplier_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s or None