"""Attachments router: upload, download, delete."""

import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Contract, Attachment, User
from app.schemas import AttachmentResponse
from app.dependencies import get_current_user, require_manager_or_admin
from app.config import settings
from app.utils import (
    validate_attachment, get_mapped_file_type,
    generate_storage_path, log_audit,
)

router = APIRouter(prefix="/api/contracts", tags=["attachments"])


def _require_manage(current_user: User = Depends(require_manager_or_admin)):
    return current_user


@router.post("/{contract_id}/attachments", response_model=AttachmentResponse,
             status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    contract_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manage),
):
    """Upload an attachment to a contract."""
    # Verify contract exists
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # Read file content
    content = await file.read()

    # Validate
    is_valid, error_msg = validate_attachment(file.filename, content)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Determine file type
    file_type = get_mapped_file_type(file.filename, content)

    # Generate storage path
    storage_rel = generate_storage_path(contract_id, file.filename)
    storage_abs = os.path.join(settings.UPLOAD_DIR, storage_rel)

    # Create directories
    os.makedirs(os.path.dirname(storage_abs), exist_ok=True)

    # Write file
    with open(storage_abs, "wb") as f:
        f.write(content)

    # Create DB record
    attachment = Attachment(
        contract_id=contract_id,
        filename=storage_rel,
        original_name=file.filename,
        file_type=file_type,
        file_size=len(content),
        storage_path=storage_rel,
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    log_audit(db, current_user.id, "upload", "attachment", attachment.id,
              f"Uploaded {file.filename} ({len(content)} bytes) to contract #{contract_id}")
    db.commit()

    return attachment


@router.get("/{contract_id}/attachments/{attachment_id}")
async def download_attachment(
    contract_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download an attachment."""
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.contract_id == contract_id,
    ).first()

    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    storage_abs = os.path.join(settings.UPLOAD_DIR, attachment.storage_path)
    if not os.path.exists(storage_abs):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件文件不存在")

    return FileResponse(
        path=storage_abs,
        filename=attachment.original_name,
        media_type="application/octet-stream",
    )


@router.delete("/{contract_id}/attachments/{attachment_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    contract_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manage),
):
    """Delete an attachment."""
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.contract_id == contract_id,
    ).first()

    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    # Delete physical file
    storage_abs = os.path.join(settings.UPLOAD_DIR, attachment.storage_path)
    if os.path.exists(storage_abs):
        os.remove(storage_abs)

    filename = attachment.original_name
    db.delete(attachment)

    log_audit(db, current_user.id, "delete", "attachment", attachment_id,
              f"Deleted attachment {filename} from contract #{contract_id}")
    db.commit()
