"""User management routes — admin-only CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UserCreate, UserUpdate, UserResponse, UserListResponse
from app.models import User
from app.dependencies import require_admin, get_current_user
from app.auth import hash_password
from app.utils import create_audit_log

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UserListResponse)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users (admin only)."""
    users = db.query(User).order_by(User.id).all()
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=len(users),
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new user (admin only)."""
    # Check username uniqueness
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
        email=request.email,
        role=request.role,  # type: ignore[arg-type]
        status=request.status,  # type: ignore[arg-type]
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    create_audit_log(
        db, current_user,
        action="create_user",
        entity_type="user",
        entity_id=user.id,
        detail=f"创建用户 {user.username} (role={user.role.value})",
    )

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get a single user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    changed = []

    if request.display_name is not None:
        user.display_name = request.display_name
        changed.append(f"display_name={request.display_name}")

    if request.email is not None:
        user.email = request.email
        changed.append(f"email={request.email}")

    if request.role is not None:
        user.role = request.role  # type: ignore[arg-type]
        changed.append(f"role={request.role}")

    if request.status is not None:
        user.status = request.status  # type: ignore[arg-type]
        changed.append(f"status={request.status}")

    if request.password is not None:
        user.password_hash = hash_password(request.password)
        changed.append("password=***")

    if changed:
        db.commit()
        db.refresh(user)
        create_audit_log(
            db, current_user,
            action="update_user",
            entity_type="user",
            entity_id=user.id,
            detail=f"更新用户 {user.username}: {', '.join(changed)}",
        )

    return UserResponse.model_validate(user)
