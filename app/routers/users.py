"""Users router: admin CRUD for user management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserStatus
from app.schemas import UserCreate, UserUpdate, UserResponse
from app.auth import hash_password
from app.dependencies import require_admin
from app.utils import log_audit

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users (admin only)."""
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new user (admin only)."""
    # Check for duplicate username
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        email=data.email,
        role=data.role,
        status=data.status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit(db, current_user.id, "create", "user", user.id,
              f"Created user {user.username} with role {user.role.value}")
    db.commit()

    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    changes = []
    if data.password is not None:
        user.password_hash = hash_password(data.password)
        changes.append("password")
    if data.display_name is not None:
        user.display_name = data.display_name
        changes.append("display_name")
    if data.email is not None:
        user.email = data.email
        changes.append("email")
    if data.role is not None:
        user.role = data.role
        changes.append(f"role={data.role.value}")
    if data.status is not None:
        user.status = data.status
        changes.append(f"status={data.status.value}")

    db.commit()
    db.refresh(user)

    if changes:
        log_audit(db, current_user.id, "update", "user", user.id,
                  f"Updated {', '.join(changes)} for user {user.username}")
        db.commit()

    return user
