"""Attachment management routes — upload, download, delete."""

import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AttachmentResponse
from app.models import Attachment, Contract, User
from app.dependencies import get_current_user, require_manager_or_admin
from app.utils import validate_attachment, create_audit_log
from app.config import settings

router = APIRouter(prefix="/api/contracts/{contract_id}/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    contract_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Upload an attachment to a contract (manager or admin).

    Validates file type (pdf/doc/docx) by extension and magic bytes.
    Max file size: 10MB.
    """
    # Verify contract exists
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # Validate file
    file_type, safe_filename = validate_attachment(file)

    # Create storage directory
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(contract_id))
    os.makedirs(upload_dir, exist_ok=True)

    # Determine file size
    file.file.seek(0, 2)  # seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # reset to beginning

    # Save file
    storage_path = os.path.join(upload_dir, safe_filename)
    with open(storage_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create DB record
    attachment = Attachment(
        contract_id=contract_id,
        filename=safe_filename,
        original_name=file.filename or "unknown",
        file_type=file_type,
        file_size=file_size,
        storage_path=storage_path,
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    create_audit_log(
        db, current_user,
        action="upload_attachment",
        entity_type="attachment",
        entity_id=attachment.id,
        detail=f"上传附件 {attachment.original_name} 到合同 {contract.contract_no}",
    )

    return AttachmentResponse.model_validate(attachment)


@router.get("/{attachment_id}")
def download_attachment(
    contract_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download an attachment (all authenticated users)."""
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.contract_id == contract_id,
    ).first()

    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    if not os.path.exists(attachment.storage_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件文件丢失")

    return FileResponse(
        path=attachment.storage_path,
        filename=attachment.original_name,
        media_type="application/octet-stream",
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    contract_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Delete an attachment (manager or admin)."""
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.contract_id == contract_id,
    ).first()

    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    # Delete file from disk
    if os.path.exists(attachment.storage_path):
        os.remove(attachment.storage_path)

    original_name = attachment.original_name
    db.delete(attachment)
    db.commit()

    create_audit_log(
        db, current_user,
        action="delete_attachment",
        entity_type="attachment",
        entity_id=attachment_id,
        detail=f"删除附件 {original_name}",
    )
