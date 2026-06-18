"""Auth router: login endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status, Form, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserStatus
from app.schemas import LoginRequest, LoginResponse, UserResponse
from app.auth import verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate user and return a JWT token.

    Supports JSON body (fetch/SPA) and form-encoded (SSR).
    Sets a cookie for SSR pages.
    """
    content_type = request.headers.get("content-type", "")
    redirect = None

    if "application/json" in content_type:
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")
    else:
        form_data = await request.form()
        username = str(form_data.get("username", ""))
        password = str(form_data.get("password", ""))
        redirect = str(form_data.get("redirect", "")) or None
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名和密码不能为空",
        )

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

    # For form-based login from SSR, redirect to contracts
    if redirect:
        from starlette.responses import RedirectResponse
        from app.config import settings
        redirect = redirect or f"{settings.BASE_PATH}/contracts"
        resp = RedirectResponse(url=redirect, status_code=302)
        resp.set_cookie(
            key="access_token",
            value=token,
            httponly=False,
            max_age=8 * 3600,
            path="/",
        )
        return resp

    # JSON response for SPA-style API calls
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
    return resp
