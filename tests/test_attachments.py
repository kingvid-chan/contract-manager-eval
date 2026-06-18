"""Tests for attachment upload, download, and delete endpoints."""

import os
import io
import pytest
from fastapi import status


# ── Helper: create a valid PDF-like file (starts with %PDF-) ────────────

def _pdf_bytes():
    return b"%PDF-1.4\nThis is a test PDF file.\n\x00\x00"


def _docx_bytes():
    """DOCX files are ZIP archives starting with PK."""
    # Minimal ZIP local file header
    return b"PK\x03\x04" + b"\x00" * 26


def _doc_bytes():
    """DOC files are OLE2 starting with D0CF11E0."""
    return b"\xD0\xCF\x11\xE0" + b"\x00" * 508


def _invalid_bytes():
    return b"Just some plain text file content."


# ── Helper: get a contract ID for testing ────────────────────────────────

@pytest.fixture
def contract_id(client, auth_headers):
    """Create a test contract and return its ID."""
    r = client.post("/api/contracts", json={
        "contract_no": "HT-ATTACH-TEST",
        "title": "附件测试合同",
        "party_a": "甲方",
        "party_b": "乙方",
    }, headers=auth_headers["admin"])
    assert r.status_code == 201
    return r.json()["id"]


# ── Upload Tests ─────────────────────────────────────────────────────────

class TestAttachmentUpload:
    """POST /api/contracts/{id}/attachments — upload attachment."""

    def test_admin_can_upload_pdf(self, client, auth_headers, contract_id):
        """Admin should be able to upload a PDF file."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 201
        data = r.json()
        assert data["original_name"] == "test.pdf"
        assert data["file_type"] in ("pdf", "docx", "doc")
        assert data["contract_id"] == contract_id
        assert "id" in data

    def test_manager_can_upload_docx(self, client, auth_headers, contract_id):
        """Manager should be able to upload a DOCX file."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("document.docx", io.BytesIO(_docx_bytes()),
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=auth_headers["manager"],
        )
        assert r.status_code == 201

    def test_admin_can_upload_doc(self, client, auth_headers, contract_id):
        """Admin should be able to upload a DOC file."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("legacy.doc", io.BytesIO(_doc_bytes()), "application/msword")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 201

    def test_upload_invalid_extension(self, client, auth_headers, contract_id):
        """Files with .txt extension should be rejected."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("malware.txt", io.BytesIO(_pdf_bytes()), "text/plain")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 400
        assert "不允许" in r.json()["detail"]

    def test_upload_invalid_magic_bytes(self, client, auth_headers, contract_id):
        """Files with .pdf extension but wrong magic bytes should be rejected."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("fake.pdf", io.BytesIO(_invalid_bytes()), "application/pdf")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 400

    def test_upload_oversized_file(self, client, auth_headers, contract_id, monkeypatch):
        """Files larger than MAX_UPLOAD_SIZE (10MB) should be rejected."""
        from app.config import settings
        # Temporarily lower the limit
        monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 100)

        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("big.pdf", io.BytesIO(b"%PDF-1.4\n" + b"x" * 200), "application/pdf")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 400
        assert "过大" in r.json()["detail"] or "MB" in r.json()["detail"]

    def test_viewer_cannot_upload(self, client, auth_headers, contract_id):
        """Viewer should get 403 when uploading."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers["viewer"],
        )
        assert r.status_code == 403

    def test_upload_to_nonexistent_contract(self, client, auth_headers):
        """Upload to non-existent contract should return 404."""
        r = client.post(
            "/api/contracts/99999/attachments",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 404

    def test_upload_without_file(self, client, auth_headers, contract_id):
        """Request without file should return 422."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            headers=auth_headers["admin"],
        )
        assert r.status_code == 422


# ── Download Tests ───────────────────────────────────────────────────────

class TestAttachmentDownload:
    """GET /api/contracts/{id}/attachments/{aid} — download attachment."""

    @pytest.fixture
    def uploaded_attachment(self, client, auth_headers, contract_id):
        """Upload a PDF and return (contract_id, attachment_id)."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("download-test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 201
        data = r.json()
        return contract_id, data["id"]

    def test_admin_can_download(self, client, auth_headers, uploaded_attachment):
        """Admin should be able to download an attachment."""
        cid, aid = uploaded_attachment
        r = client.get(f"/api/contracts/{cid}/attachments/{aid}",
                       headers=auth_headers["admin"])
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_viewer_can_download(self, client, auth_headers, uploaded_attachment):
        """Viewer should be able to download an attachment."""
        cid, aid = uploaded_attachment
        r = client.get(f"/api/contracts/{cid}/attachments/{aid}",
                       headers=auth_headers["viewer"])
        assert r.status_code == 200

    def test_download_nonexistent_attachment(self, client, auth_headers, contract_id):
        """Download non-existent attachment should return 404."""
        r = client.get(f"/api/contracts/{contract_id}/attachments/99999",
                       headers=auth_headers["admin"])
        assert r.status_code == 404

    def test_download_wrong_contract(self, client, auth_headers, uploaded_attachment):
        """Download attachment with wrong contract_id should return 404."""
        _, aid = uploaded_attachment
        r = client.get(f"/api/contracts/99999/attachments/{aid}",
                       headers=auth_headers["admin"])
        assert r.status_code == 404


# ── Delete Tests ─────────────────────────────────────────────────────────

class TestAttachmentDelete:
    """DELETE /api/contracts/{id}/attachments/{aid} — delete attachment."""

    @pytest.fixture
    def uploaded_attachment(self, client, auth_headers, contract_id):
        """Upload a PDF and return (contract_id, attachment_id)."""
        r = client.post(
            f"/api/contracts/{contract_id}/attachments",
            files={"file": ("delete-test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers["admin"],
        )
        assert r.status_code == 201
        data = r.json()
        return contract_id, data["id"]

    def test_admin_can_delete_attachment(self, client, auth_headers, uploaded_attachment):
        """Admin should be able to delete an attachment."""
        cid, aid = uploaded_attachment
        r = client.delete(f"/api/contracts/{cid}/attachments/{aid}",
                          headers=auth_headers["admin"])
        assert r.status_code == 204

        # Verify it's gone
        r = client.get(f"/api/contracts/{cid}/attachments/{aid}",
                       headers=auth_headers["admin"])
        assert r.status_code == 404

    def test_manager_can_delete_attachment(self, client, auth_headers, uploaded_attachment):
        """Manager should be able to delete an attachment."""
        cid, aid = uploaded_attachment
        r = client.delete(f"/api/contracts/{cid}/attachments/{aid}",
                          headers=auth_headers["manager"])
        assert r.status_code == 204

    def test_viewer_cannot_delete_attachment(self, client, auth_headers, uploaded_attachment):
        """Viewer should get 403 when deleting."""
        cid, aid = uploaded_attachment
        r = client.delete(f"/api/contracts/{cid}/attachments/{aid}",
                          headers=auth_headers["viewer"])
        assert r.status_code == 403

    def test_delete_nonexistent_attachment(self, client, auth_headers, contract_id):
        """Delete non-existent attachment should return 404."""
        r = client.delete(f"/api/contracts/{contract_id}/attachments/99999",
                          headers=auth_headers["admin"])
        assert r.status_code == 404
