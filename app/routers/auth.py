"""Auth router: login endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status, Form, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserStatus
from app.schemas import LoginRequest, LoginResponse, UserResponse
from app.auth import verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(
    response: Response,
    username: str = Form(None),
    password: str = Form(None),
    db: Session = Depends(get_db),
    redirect: str = Form(None),
):
    """Authenticate user and return a JWT token.

    Supports both form-encoded (SSR) and redirect pattern.
    Sets a cookie for SSR pages.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if user.status == UserStatus.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})

    # Set cookie for SSR pages
    resp = JSONResponse(content={
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role.value,
            "status": user.status.value,
            "created_at": user.created_at.isoformat(),
        },
    })
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=False,  # Allow JS access for SPA-style API calls
        max_age=8 * 3600,
        path="/",
    )

    # If this is a form-based login from SSR, redirect to contracts
    if redirect is not None:
        from starlette.responses import RedirectResponse
        from app.config import settings
        dest = redirect or f"{settings.BASE_PATH}/contracts"
        resp = RedirectResponse(url=dest, status_code=302)
        resp.set_cookie(
            key="access_token",
            value=token,
            httponly=False,
            max_age=8 * 3600,
            path="/",
        )

    return resp
