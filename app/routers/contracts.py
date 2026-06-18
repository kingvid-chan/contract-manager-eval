"""Contracts router: CRUD + state transitions."""

import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Contract, ContractStatus, User, UserRole, Attachment
from app.schemas import (
    ContractCreate, ContractUpdate, ContractResponse,
    ContractDetailResponse, TransitionRequest, AttachmentResponse,
)
from app.dependencies import get_current_user, require_manager_or_admin, require_admin
from app.utils import log_audit

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _require_manage_access(current_user: User = Depends(require_manager_or_admin)):
    """Dependency: manager or admin for write operations."""
    return current_user


# ── Transition logic ───────────────────────────────────────────────────

VALID_TRANSITIONS = {
    ContractStatus.draft: {ContractStatus.pending, ContractStatus.terminated},
    ContractStatus.pending: {ContractStatus.signed, ContractStatus.draft},
    ContractStatus.signed: {ContractStatus.terminated, ContractStatus.expired},
}

TRANSITION_LABELS = {
    "pending": "提交审批",
    "signed": "签署",
    "terminated": "终止",
    "expired": "过期",
    "draft": "退回",
}


def _apply_auto_expired(contract: Contract) -> bool:
    """Check if a signed contract has passed its end_date and mark expired."""
    if contract.status == ContractStatus.signed and contract.end_date:
        now = datetime.datetime.utcnow()
        if contract.end_date < now:
            contract.status = ContractStatus.expired
            return True
    return False


# ── Routes ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[ContractResponse])
def list_contracts(
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, alias="q"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List contracts with optional status filter and search."""
    query = db.query(Contract)

    if status_filter:
        query = query.filter(Contract.status == status_filter)

    if q:
        search = f"%{q}%"
        query = query.filter(
            (Contract.contract_no.like(search)) | (Contract.title.like(search))
        )

    contracts = query.order_by(Contract.updated_at.desc()).all()

    # Auto-expire signed contracts past end_date
    for c in contracts:
        _apply_auto_expired(c)
    db.commit()

    return contracts


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    data: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manage_access),
):
    """Create a new contract."""
    # Check for duplicate contract number
    existing = db.query(Contract).filter(Contract.contract_no == data.contract_no).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="合同编号已存在",
        )

    contract = Contract(
        contract_no=data.contract_no,
        title=data.title,
        party_a=data.party_a,
        party_b=data.party_b,
        amount=data.amount,
        status=ContractStatus.draft,
        description=data.description,
        created_by=current_user.id,
    )

    # Handle date fields
    for field_name in ("sign_date", "start_date", "end_date"):
        value = getattr(data, field_name)
        if value:
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    value = datetime.datetime.strptime(value, "%Y-%m-%d")
            setattr(contract, field_name, value)

    db.add(contract)
    db.commit()
    db.refresh(contract)

    log_audit(db, current_user.id, "create", "contract", contract.id,
              f"Created contract {contract.contract_no}")
    db.commit()

    return contract


@router.get("/{contract_id}", response_model=ContractDetailResponse)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get contract detail with attachments."""
    contract = db.query(Contract).options(
        joinedload(Contract.creator),
        joinedload(Contract.attachments),
    ).filter(Contract.id == contract_id).first()

    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    _apply_auto_expired(contract)
    db.commit()

    return contract


@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: int,
    data: ContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manage_access),
):
    """Update a contract."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    changes = []
    for field_name in ("title", "party_a", "party_b", "amount", "description",
                       "sign_date", "start_date", "end_date"):
        value = getattr(data, field_name)
        if value is not None:
            # Parse date strings
            if field_name in ("sign_date", "start_date", "end_date"):
                if isinstance(value, str):
                    try:
                        value = datetime.datetime.fromisoformat(value)
                    except (ValueError, TypeError):
                        value = datetime.datetime.strptime(value, "%Y-%m-%d")
            setattr(contract, field_name, value)
            changes.append(field_name)

    db.commit()
    db.refresh(contract)

    if changes:
        log_audit(db, current_user.id, "update", "contract", contract.id,
                  f"Updated {', '.join(changes)} for contract {contract.contract_no}")
        db.commit()

    return contract


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a contract (admin only)."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    contract_no = contract.contract_no
    db.delete(contract)

    log_audit(db, current_user.id, "delete", "contract", contract_id,
              f"Deleted contract {contract_no}")
    db.commit()


@router.post("/{contract_id}/transition", response_model=ContractResponse)
def transition_contract(
    contract_id: int,
    data: TransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manage_access),
):
    """Transition a contract to a new status."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    # Check auto-expire
    _apply_auto_expired(contract)

    try:
        target_status = ContractStatus(data.action)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的状态操作: {data.action}",
        )

    # Validate transition
    allowed = VALID_TRANSITIONS.get(contract.status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不允许从 {contract.status.value} 转换到 {data.action}（只能转到: {[s.value for s in allowed]}）",
        )

    # Special handling for signed → expired
    if target_status == ContractStatus.expired and contract.end_date:
        now = datetime.datetime.utcnow()
        if contract.end_date >= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="合同尚未到期，不能手动设为过期",
            )

    old_status = contract.status.value
    contract.status = target_status

    # Set sign_date when transitioning to signed
    if target_status == ContractStatus.signed and not contract.sign_date:
        contract.sign_date = datetime.datetime.utcnow()

    db.commit()
    db.refresh(contract)

    action_label = TRANSITION_LABELS.get(data.action, data.action)
    log_audit(db, current_user.id, "transition", "contract", contract.id,
              f"Changed contract {contract.contract_no} status from {old_status} to {data.action}")
    db.commit()

    return contract
