"""Utility functions for file validation, audit logging, etc."""

import os
import uuid

from app.config import settings

# ── File type constants ────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}

MAGIC_BYTES = {
    b"%PDF": "pdf",
}

ZIP_MAGIC = b"PK\x03\x04"  # ZIP (DOCX is a ZIP)


def allowed_file_extension(filename: str) -> bool:
    """Check if the file extension is in the allowed list."""
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def get_file_type_by_magic(content: bytes) -> str | None:
    """Determine file type from magic bytes.

    Returns one of 'pdf', 'doc', 'docx' or None.
    """
    if len(content) < 4:
        return None

    # Check DOCX first (ZIP-based)
    if content[:4] == ZIP_MAGIC or content[:2] == b"PK":
        return "docx"

    # Check PDF
    if content[:4] == b"%PDF":
        return "pdf"

    # Check OLE2 DOC
    if content[:4] == b"\xD0\xCF\x11\xE0" or content[:8] == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        return "doc"

    return None


def validate_attachment(filename: str, content: bytes) -> tuple[bool, str]:
    """Validate an attachment file.

    Returns (is_valid, error_message).
    """
    # Check extension
    if not allowed_file_extension(filename):
        return False, f"不允许的文件类型。仅支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

    # Check file size
    if len(content) > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        return False, f"文件过大，最大允许 {max_mb:.0f}MB"

    # Check magic bytes
    detected_type = get_file_type_by_magic(content)
    if detected_type is None:
        return False, "无法识别的文件格式"

    # Match extension with detected magic
    ext = os.path.splitext(filename.lower())[1][1:]  # remove dot
    if ext == "docx" and detected_type == "docx":
        pass  # OK
    elif ext == "pdf" and detected_type != "pdf":
        return False, "文件扩展名与内容不匹配（期望 PDF）"
    elif ext == "doc" and detected_type not in ("doc", "docx"):
        return False, "文件扩展名与内容不匹配（期望 DOC）"

    return True, ""


def get_mapped_file_type(filename: str, content: bytes) -> str:
    """Return the canonical file_type string for storage."""
    ext = os.path.splitext(filename.lower())[1][1:]
    if ext == "docx":
        return "docx"
    detected = get_file_type_by_magic(content)
    if detected:
        return detected
    return "unknown"


def generate_storage_path(contract_id: int, original_name: str) -> str:
    """Generate a unique storage path for an uploaded file."""
    unique_id = uuid.uuid4().hex[:12]
    safe_name = f"{unique_id}_{original_name}"
    return os.path.join(str(contract_id), safe_name)


def log_audit(db, user_id: int, action: str, entity_type: str,
              entity_id: int | None = None, detail: str | None = None):
    """Create an audit log entry."""
    from app.models import AuditLog

    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    )
    db.add(log_entry)
