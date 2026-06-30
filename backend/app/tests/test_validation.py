"""Unit tests for validation warnings + confidence (§12, §18)."""
from datetime import date

from app.invoices import validation as v


def test_required_fields_missing():
    warnings = v.check_required_fields({})
    codes = [w.code for w in warnings]
    assert "missing_supplier_name" in codes
    assert "missing_invoice_number" in codes
    assert "missing_total_amount" in codes
    assert "missing_currency" in codes
    assert all(w.severity == "warning" for w in warnings)


def test_required_fields_present():
    fields = {"supplier_name": "X", "invoice_number": "1", "invoice_date": date(2026, 1, 1),
              "total_amount": 100, "currency": "EUR"}
    assert v.check_required_fields(fields) == []


def test_amount_mismatch_error():
    warnings = v.check_amounts({"subtotal_amount": 100, "tax_amount": 20, "total_amount": 130})
    assert any(w.code == "subtotal_tax_total_mismatch" and w.severity == "error" for w in warnings)


def test_amount_match_ok():
    assert v.check_amounts({"subtotal_amount": 100, "tax_amount": 20, "total_amount": 120}) == []


def test_amount_tolerance():
    # within 0.02 tolerance
    assert v.check_amounts({"subtotal_amount": 100, "tax_amount": 20, "total_amount": 120.01}) == []


def test_due_before_invoice():
    warnings = v.check_dates({"invoice_date": date(2026, 6, 23), "due_date": date(2026, 6, 1)})
    assert any(w.code == "due_before_invoice" for w in warnings)


def test_implausible_invoice_date():
    warnings = v.check_dates({"invoice_date": date(1990, 1, 1)})
    assert any(w.code == "implausible_invoice_date" for w in warnings)


def test_vat_format_ok():
    assert v.check_vat_format({"supplier_vat_number": "FR12345678901"}) == []


def test_vat_format_bad():
    warnings = v.check_vat_format({"supplier_vat_number": "???"})
    assert any(w.code == "invalid_vat_format" for w in warnings)


def test_generate_warnings_aggregates():
    warnings = v.generate_warnings({})
    codes = [w.code for w in warnings]
    assert "missing_total_amount" in codes


def test_confidence_weighting():
    per_field = {
        "invoice_number": 1.0, "supplier_name": 1.0, "invoice_date": 1.0,
        "total_amount": 1.0, "tax_amount": 1.0, "subtotal_amount": 1.0, "currency": 1.0,
    }
    assert v.compute_overall_confidence(per_field) == 1.0


def test_confidence_partial():
    per_field = {"total_amount": 1.0}  # weight 0.25 only
    conf = v.compute_overall_confidence(per_field)
    assert 0.0 < conf <= 1.0


def test_duplicate_by_number():
    rows = [{"id": "a", "supplier_name": "X", "invoice_number": "FA-1", "document_hash": "h1",
             "total_amount": 100, "invoice_date": date(2026, 1, 1)}]
    new = {"id": "b", "supplier_name": "X", "invoice_number": "FA-1", "document_hash": "h2",
           "total_amount": 100, "invoice_date": date(2026, 1, 1)}
    assert v.detect_duplicates(rows, new) == "duplicate_invoice_detected"


def test_duplicate_by_hash():
    rows = [{"id": "a", "supplier_name": "X", "invoice_number": "FA-1", "document_hash": "h1",
             "total_amount": 100, "invoice_date": date(2026, 1, 1)}]
    new = {"id": "b", "supplier_name": "Y", "invoice_number": "FA-2", "document_hash": "h1",
           "total_amount": 200, "invoice_date": date(2026, 2, 1)}
    assert v.detect_duplicates(rows, new) == "duplicate_invoice_detected"


def test_no_duplicate():
    rows = [{"id": "a", "supplier_name": "X", "invoice_number": "FA-1", "document_hash": "h1",
             "total_amount": 100, "invoice_date": date(2026, 1, 1)}]
    new = {"id": "b", "supplier_name": "Y", "invoice_number": "FA-2", "document_hash": "h2",
           "total_amount": 200, "invoice_date": date(2026, 2, 1)}
    assert v.detect_duplicates(rows, new) is None