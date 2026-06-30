"""Tests for storage path generation + file validation (§18)."""
from app.invoices import service
from app.invoices.service import ALLOWED_MIME, MAX_FILE_SIZE


def test_storage_key_is_namespaced():
    key = service.build_storage_key("org-uuid", "inv-uuid", "Facture 2026.pdf")
    assert key.startswith("org-uuid/originals/inv-uuid/")
    assert "/" not in key.split("inv-uuid/")[1]  # safe filename


def test_storage_key_sanitizes_unsafe_chars():
    key = service.build_storage_key("org", "inv", "../../etc/passwd")
    # Path traversal is neutralized: slashes become underscores so the result is
    # a single filename component under the org/originals/inv/ prefix.
    parts = key.split("/")
    assert parts == ["org", "originals", "inv", parts[-1]]
    assert "/" not in parts[-1]  # no traversal possible
    assert parts[-1]  # non-empty


def test_compute_hash_deterministic():
    a = service.compute_hash(b"hello")
    b = service.compute_hash(b"hello")
    c = service.compute_hash(b"world")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_allowed_mime_covers_common_types():
    assert "application/pdf" in ALLOWED_MIME
    assert "image/jpeg" in ALLOWED_MIME
    assert "image/png" in ALLOWED_MIME
    assert "image/tiff" in ALLOWED_MIME


def test_max_file_size_is_25mb():
    assert MAX_FILE_SIZE == 25 * 1024 * 1024


def test_role_permissions_sets():
    # uploaders exclude viewers
    assert "viewer" not in service.ROLES_CAN_UPLOAD
    assert "member" in service.ROLES_CAN_UPLOAD
    # hard delete is owner-only
    assert service.ROLES_CAN_DELETE == {"owner"}