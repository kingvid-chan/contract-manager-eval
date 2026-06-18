"""Contract management routes — CRUD + state transitions."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.schemas import (
    ContractCreate,
    ContractUpdate,
    ContractStatusTransition,
    ContractResponse,
    ContractListResponse,
)
from app.models import Contract, ContractStatus, User, UserRole
from app.dependencies import get_current_user, require_manager_or_admin, require_admin
from app.utils import create_audit_log

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

# Valid status transitions
VALID_TRANSITIONS: dict[ContractStatus, set[ContractStatus]] = {
    ContractStatus.draft: {ContractStatus.pending, ContractStatus.terminated},
    ContractStatus.pending: {ContractStatus.signed, ContractStatus.draft},
    ContractStatus.signed: {ContractStatus.terminated, ContractStatus.expired},
    ContractStatus.terminated: set(),
    ContractStatus.expired: set(),
}


def _contract_to_response(contract: Contract, creator: User | None = None) -> ContractResponse:
    """Convert a Contract ORM object to a ContractResponse dict."""
    return ContractResponse(
        id=contract.id,
        contract_no=contract.contract_no,
        title=contract.title,
        party_a=contract.party_a,
        party_b=contract.party_b,
        amount=contract.amount,
        status=contract.status.value if contract.status else "draft",
        sign_date=contract.sign_date,
        start_date=contract.start_date,
        end_date=contract.end_date,
        description=contract.description,
        created_by=contract.created_by,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
        creator_name=creator.display_name if creator else None,
    )


@router.get("", response_model=ContractListResponse)
def list_contracts(
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, alias="q"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List contracts with optional status and search filters."""
    query = db.query(Contract).options(joinedload(Contract.creator))

    if status_filter:
        query = query.filter(Contract.status == status_filter)

    if q:
        like_pattern = f"%{q}%"
        query = query.filter(
            (Contract.contract_no.ilike(like_pattern)) |
            (Contract.title.ilike(like_pattern))
        )

    contracts = query.order_by(Contract.updated_at.desc()).all()

    return ContractListResponse(
        contracts=[_contract_to_response(c, c.creator) for c in contracts],
        total=len(contracts),
    )


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    request: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Create a new contract (manager or admin)."""
    # Check contract_no uniqueness
    existing = db.query(Contract).filter(Contract.contract_no == request.contract_no).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="合同编号已存在",
        )

    contract = Contract(
        contract_no=request.contract_no,
        title=request.title,
        party_a=request.party_a,
        party_b=request.party_b,
        amount=request.amount,
        status=request.status,  # type: ignore[arg-type]
        sign_date=request.sign_date,
        start_date=request.start_date,
        end_date=request.end_date,
        description=request.description,
        created_by=current_user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    create_audit_log(
        db, current_user,
        action="create_contract",
        entity_type="contract",
        entity_id=contract.id,
        detail=f"创建合同 {contract.contract_no}",
    )

    return _contract_to_response(contract, current_user)


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single contract by ID."""
    contract = db.query(Contract).options(joinedload(Contract.creator)).filter(
        Contract.id == contract_id
    ).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")
    return _contract_to_response(contract, contract.creator)


@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: int,
    request: ContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Update a contract (manager or admin)."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    changed = []

    if request.contract_no is not None:
        existing = db.query(Contract).filter(
            Contract.contract_no == request.contract_no,
            Contract.id != contract_id,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="合同编号已存在")
        contract.contract_no = request.contract_no
        changed.append(f"contract_no={request.contract_no}")

    for field in ["title", "party_a", "party_b", "amount", "sign_date",
                   "start_date", "end_date", "description"]:
        val = getattr(request, field, None)
        if val is not None:
            setattr(contract, field, val)
            changed.append(f"{field}={val}")

    if changed:
        db.commit()
        db.refresh(contract)
        create_audit_log(
            db, current_user,
            action="update_contract",
            entity_type="contract",
            entity_id=contract.id,
            detail=f"更新合同 {contract.contract_no}: {', '.join(changed)}",
        )

    return _contract_to_response(contract, current_user)


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
    db.commit()

    create_audit_log(
        db, current_user,
        action="delete_contract",
        entity_type="contract",
        entity_id=contract_id,
        detail=f"删除合同 {contract_no}",
    )


@router.post("/{contract_id}/transition", response_model=ContractResponse)
def transition_contract(
    contract_id: int,
    request: ContractStatusTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Transition a contract's status (manager or admin).

    Valid transitions:
        draft → pending, terminated
        pending → signed, draft
        signed → terminated, expired
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    try:
        target = ContractStatus(request.target_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的状态: {request.target_status}",
        )

    current_status = contract.status
    allowed = VALID_TRANSITIONS.get(current_status, set())

    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不允许从 {current_status.value} 转换到 {target.value}",
        )

    old_status = contract.status.value
    contract.status = target
    db.commit()
    db.refresh(contract)

    create_audit_log(
        db, current_user,
        action="transition_contract",
        entity_type="contract",
        entity_id=contract.id,
        detail=f"合同 {contract.contract_no} 状态: {old_status} → {target.value}",
    )

    return _contract_to_response(contract, current_user)
