"""FastAPI application entry point — contract management system."""

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware import CacheControlMiddleware
from app.routers import auth, users, contracts, attachments
from app.models import User, UserRole
from app.dependencies import get_current_user, get_token_from_request
from app.auth import decode_access_token

app = FastAPI(title="合同管理系统", version="0.0.1")

# Add Cache-Control middleware (must be added before other middleware)
app.add_middleware(CacheControlMiddleware)

# Include API routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(contracts.router)
app.include_router(attachments.router)

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Static files — served under BASE_PATH/static/
# Mount path must be relative to BASE_PATH when behind Nginx proxy
app.mount(
    f"{settings.BASE_PATH}/static",
    StaticFiles(directory="static"),
    name="static",
)


def get_template_context(request: Request, db: Session) -> dict:
    """Build common template context including current user info."""
    token = get_token_from_request(request)
    user = None
    if token:
        payload = decode_access_token(token)
        if payload:
            user = db.query(User).filter(User.id == int(payload["sub"])).first()
    return {
        "request": request,
        "user": user,
        "base_path": settings.BASE_PATH,
        "version": "0.0.1",
        "is_admin": user is not None and user.role == UserRole.admin,
        "is_manager_or_admin": user is not None and user.role in (UserRole.admin, UserRole.manager),
    }


# ── Frontend page routes ──────────────────────────────────────────────

@app.get(f"{settings.BASE_PATH}/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Render login page."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "base_path": settings.BASE_PATH,
        "version": "0.0.1",
    })


@app.get(f"{settings.BASE_PATH}/", response_class=HTMLResponse)
def contracts_list_page(request: Request, db: Session = Depends(get_db)):
    """Render contracts list page (home page)."""
    ctx = get_template_context(request, db)
    if ctx["user"] is None:
        return RedirectResponse(url=f"{settings.BASE_PATH}/login")
    return templates.TemplateResponse("contracts/list.html", ctx)


@app.get(f"{settings.BASE_PATH}/contracts/new", response_class=HTMLResponse)
def contract_create_page(request: Request, db: Session = Depends(get_db)):
    """Render contract creation form."""
    ctx = get_template_context(request, db)
    if ctx["user"] is None:
        return RedirectResponse(url=f"{settings.BASE_PATH}/login")
    if not ctx["is_manager_or_admin"]:
        return HTMLResponse("无权限", status_code=403)
    return templates.TemplateResponse("contracts/form.html", {**ctx, "contract": None})


@app.get(f"{settings.BASE_PATH}/contracts/{{contract_id}}", response_class=HTMLResponse)
def contract_detail_page(contract_id: int, request: Request, db: Session = Depends(get_db)):
    """Render contract detail page with attachments."""
    ctx = get_template_context(request, db)
    if ctx["user"] is None:
        return RedirectResponse(url=f"{settings.BASE_PATH}/login")
    from app.models import Contract
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        return HTMLResponse("合同不存在", status_code=404)
    return templates.TemplateResponse("contracts/detail.html", {**ctx, "contract": contract})


@app.get(f"{settings.BASE_PATH}/contracts/{{contract_id}}/edit", response_class=HTMLResponse)
def contract_edit_page(contract_id: int, request: Request, db: Session = Depends(get_db)):
    """Render contract edit form."""
    ctx = get_template_context(request, db)
    if ctx["user"] is None:
        return RedirectResponse(url=f"{settings.BASE_PATH}/login")
    if not ctx["is_manager_or_admin"]:
        return HTMLResponse("无权限", status_code=403)
    from app.models import Contract
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        return HTMLResponse("合同不存在", status_code=404)
    return templates.TemplateResponse("contracts/form.html", {**ctx, "contract": contract})


@app.get(f"{settings.BASE_PATH}/users", response_class=HTMLResponse)
def users_list_page(request: Request, db: Session = Depends(get_db)):
    """Render user management page (admin only)."""
    ctx = get_template_context(request, db)
    if ctx["user"] is None:
        return RedirectResponse(url=f"{settings.BASE_PATH}/login")
    if not ctx["is_admin"]:
        return HTMLResponse("无权限", status_code=403)
    users_list = db.query(User).order_by(User.id).all()
    return templates.TemplateResponse("users/list.html", {**ctx, "users": users_list})


@app.get(f"{settings.BASE_PATH}/users/new", response_class=HTMLResponse)
def user_create_page(request: Request, db: Session = Depends(get_db)):
    """Render user creation form (admin only)."""
    ctx = get_template_context(request, db)
    if ctx["user"] is None:
        return RedirectResponse(url=f"{settings.BASE_PATH}/login")
    if not ctx["is_admin"]:
        return HTMLResponse("无权限", status_code=403)
    return templates.TemplateResponse("users/form.html", {**ctx, "edit_user": None})


@app.get(f"{settings.BASE_PATH}/users/{{user_id}}/edit", response_class=HTMLResponse)
def user_edit_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    """Render user edit form (admin only)."""
    ctx = get_template_context(request, db)
    if ctx["user"] is None:
        return RedirectResponse(url=f"{settings.BASE_PATH}/login")
    if not ctx["is_admin"]:
        return HTMLResponse("无权限", status_code=403)
    edit_user = db.query(User).filter(User.id == user_id).first()
    if not edit_user:
        return HTMLResponse("用户不存在", status_code=404)
    return templates.TemplateResponse("users/form.html", {**ctx, "edit_user": edit_user})


@app.get(f"{settings.BASE_PATH}/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.0.1"}
