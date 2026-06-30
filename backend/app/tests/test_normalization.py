"""Unit tests for normalization (§11, §18)."""
from app.invoices import normalization as n


def test_normalize_amount_eu_thousand():
    assert n.normalize_amount("1 234,56") == 1234.56


def test_normalize_amount_us_thousand():
    assert n.normalize_amount("1,234.56") == 1234.56


def test_normalize_amount_plain_dot():
    assert n.normalize_amount("1234.56") == 1234.56


def test_normalize_amount_plain_comma():
    assert n.normalize_amount("1234,56") == 1234.56


def test_normalize_amount_with_symbol():
    assert n.normalize_amount("€ 1000.00") == 1000.0


def test_normalize_amount_none():
    assert n.normalize_amount(None) is None
    assert n.normalize_amount("") is None
    assert n.normalize_amount("abc") is None


def test_normalize_date_eu_slash():
    assert n.normalize_date("23/06/2026") == "2026-06-23"


def test_normalize_date_iso():
    assert n.normalize_date("2026-06-23") == "2026-06-23"


def test_normalize_date_eu_dot():
    assert n.normalize_date("23.06.2026") == "2026-06-23"


def test_normalize_date_invalid():
    assert n.normalize_date("not a date") is None
    assert n.normalize_date(None) is None


def test_normalize_currency_symbol():
    assert n.normalize_currency("€") == "EUR"
    assert n.normalize_currency("$") == "USD"
    assert n.normalize_currency("£") == "GBP"


def test_normalize_currency_code():
    assert n.normalize_currency("eur") == "EUR"
    assert n.normalize_currency("MAD") == "MAD"


def test_normalize_currency_none():
    assert n.normalize_currency(None) is None
    assert n.normalize_currency("XYZ") is None


def test_normalize_vat():
    assert n.normalize_vat("fr 12 34 56 78 901") == "FR12345678901"
    assert n.normalize_vat("DE123456789") == "DE123456789"
    assert n.normalize_vat(None) is None


def test_normalize_supplier_name():
    assert n.normalize_supplier_name("  Example   SARL  ") == "Example SARL"
    assert n.normalize_supplier_name(None) is None