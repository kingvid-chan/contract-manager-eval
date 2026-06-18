"""FastAPI application entry point for the Contract Manager system."""

import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, engine, Base, SessionLocal
from app.models import Contract, ContractStatus, User, UserStatus, UserRole, Attachment, AuditLog
from app.middleware import CacheControlMiddleware
from app.auth import verify_password, create_access_token
from app.dependencies import get_current_user, get_token_from_request
from app.utils import log_audit

# ── Application ────────────────────────────────────────────────────────

app = FastAPI(title="合同管理系统", version="0.0.1")

# Middleware: must add Cache-Control: no-cache to HTML responses
app.add_middleware(CacheControlMiddleware)

# Templates
templates = Jinja2Templates(directory="templates")

# ── Static Files ───────────────────────────────────────────────────────

app.mount(
    f"{settings.BASE_PATH}/static",
    StaticFiles(directory="static"),
    name="static",
)

# ── API Routers ────────────────────────────────────────────────────────

from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.contracts import router as contracts_router
from app.routers.attachments import router as attachments_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(contracts_router)
app.include_router(attachments_router)

# ── Health Check ───────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    """Health check endpoint — returns 200."""
    return {"status": "ok", "version": "0.0.1"}


# ── SSR Helpers ────────────────────────────────────────────────────────

VERSION = "0.0.1"


def _template_context(request: Request, user: User | None = None) -> dict:
    """Build the common template context."""
    return {
        "request": request,
        "base_path": settings.BASE_PATH,
        "version": VERSION,
        "user": user,
        "user_roles": {r.value: r.value for r in UserRole},
    }


def _get_page_user(request: Request) -> User | None:
    """Extract user from cookie/token for SSR pages. Returns None if not authenticated."""
    token = get_token_from_request(request)
    if not token:
        return None
    from app.auth import decode_access_token
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user and user.status == UserStatus.disabled:
            return None
        return user
    finally:
        db.close()


def _require_page_auth(request: Request):
    """Get authenticated user for SSR page, or redirect to login."""
    user = _get_page_user(request)
    if not user:
        login_url = f"{settings.BASE_PATH}/login"
        return None, RedirectResponse(url=login_url, status_code=302)
    return user, None


# ── Frontend Page Routes ────────────────────────────────────────────────

@app.get(f"{settings.BASE_PATH}/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Render the login page."""
    user = _get_page_user(request)
    if user:
        return RedirectResponse(url=f"{settings.BASE_PATH}/contracts", status_code=302)
    return templates.TemplateResponse("login.html", _template_context(request))


@app.post(f"{settings.BASE_PATH}/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Handle login form submission for SSR."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            ctx = _template_context(request)
            ctx["error"] = "用户名或密码错误"
            return templates.TemplateResponse("login.html", ctx, status_code=401)

        if user.status == UserStatus.disabled:
            ctx = _template_context(request)
            ctx["error"] = "账户已被禁用"
            return templates.TemplateResponse("login.html", ctx, status_code=403)

        token = create_access_token(data={"sub": str(user.id), "role": user.role.value})

        resp = RedirectResponse(url=f"{settings.BASE_PATH}/contracts", status_code=302)
        resp.set_cookie(
            key="access_token",
            value=token,
            httponly=False,
            max_age=8 * 3600,
            path="/",
        )
        return resp
    finally:
        db.close()


@app.get("/")
def root():
    """Redirect root to contracts page."""
    return RedirectResponse(url=f"{settings.BASE_PATH}/contracts", status_code=302)


@app.get(f"{settings.BASE_PATH}/contracts", response_class=HTMLResponse)
def contracts_list_page(request: Request):
    """Render the contract list page."""
    user, redirect = _require_page_auth(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        status_filter = request.query_params.get("status", "")
        q = request.query_params.get("q", "")

        query = db.query(Contract)
        if status_filter:
            query = query.filter(Contract.status == status_filter)
        if q:
            search = f"%{q}%"
            query = query.filter(
                (Contract.contract_no.like(search)) | (Contract.title.like(search))
            )

        contracts = query.order_by(Contract.updated_at.desc()).all()

        # Auto-expire
        now = datetime.datetime.utcnow()
        for c in contracts:
            if c.status == ContractStatus.signed and c.end_date and c.end_date < now:
                c.status = ContractStatus.expired
        db.commit()

        ctx = _template_context(request, user)
        ctx["contracts"] = contracts
        ctx["status_filter"] = status_filter
        ctx["q"] = q
        ctx["ContractStatus"] = ContractStatus
        return templates.TemplateResponse("contracts/list.html", ctx)
    finally:
        db.close()


@app.get(f"{settings.BASE_PATH}/contracts/new", response_class=HTMLResponse)
def contract_new_page(request: Request):
    """Render the new contract form."""
    user, redirect = _require_page_auth(request)
    if redirect:
        return redirect
    if user.role == UserRole.viewer:
        raise HTTPException(status_code=403, detail="无权限创建合同")

    ctx = _template_context(request, user)
    ctx["contract"] = None
    return templates.TemplateResponse("contracts/form.html", ctx)


@app.get(f"{settings.BASE_PATH}/contracts/{{contract_id}}", response_class=HTMLResponse)
def contract_detail_page(request: Request, contract_id: int):
    """Render the contract detail page."""
    user, redirect = _require_page_auth(request)
    if redirect:
        return redirect

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="合同不存在")

        # Auto-expire
        now = datetime.datetime.utcnow()
        if contract.status == ContractStatus.signed and contract.end_date and contract.end_date < now:
            contract.status = ContractStatus.expired
            db.commit()

        attachments = db.query(Attachment).filter(Attachment.contract_id == contract_id).all()
        creator = db.query(User).filter(User.id == contract.created_by).first()

        ctx = _template_context(request, user)
        ctx["contract"] = contract
        ctx["attachments"] = attachments
        ctx["creator"] = creator
        ctx["ContractStatus"] = ContractStatus
        ctx["valid_transitions"] = {
            ContractStatus.draft: {ContractStatus.pending, ContractStatus.terminated},
            ContractStatus.pending: {ContractStatus.signed, ContractStatus.draft},
            ContractStatus.signed: {ContractStatus.terminated, ContractStatus.expired},
        }
        return templates.TemplateResponse("contracts/detail.html", ctx)
    finally:
        db.close()


@app.get(f"{settings.BASE_PATH}/contracts/{{contract_id}}/edit", response_class=HTMLResponse)
def contract_edit_page(request: Request, contract_id: int):
    """Render the edit contract form."""
    user, redirect = _require_page_auth(request)
    if redirect:
        return redirect
    if user.role == UserRole.viewer:
        raise HTTPException(status_code=403, detail="无权限编辑合同")

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="合同不存在")

        ctx = _template_context(request, user)
        ctx["contract"] = contract
        return templates.TemplateResponse("contracts/form.html", ctx)
    finally:
        db.close()


@app.get(f"{settings.BASE_PATH}/users", response_class=HTMLResponse)
def users_list_page(request: Request):
    """Render the user management page (admin only)."""
    user, redirect = _require_page_auth(request)
    if redirect:
        return redirect
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        ctx = _template_context(request, user)
        ctx["users"] = users
        ctx["UserRole"] = UserRole
        ctx["UserStatus"] = UserStatus
        return templates.TemplateResponse("users/list.html", ctx)
    finally:
        db.close()


@app.get(f"{settings.BASE_PATH}/users/new", response_class=HTMLResponse)
def user_new_page(request: Request):
    """Render the new user form (admin only)."""
    user, redirect = _require_page_auth(request)
    if redirect:
        return redirect
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    ctx = _template_context(request, user)
    ctx["edit_user"] = None
    ctx["UserRole"] = UserRole
    ctx["UserStatus"] = UserStatus
    return templates.TemplateResponse("users/form.html", ctx)


@app.get(f"{settings.BASE_PATH}/users/{{edit_id}}/edit", response_class=HTMLResponse)
def user_edit_page(request: Request, edit_id: int):
    """Render the edit user form (admin only)."""
    user, redirect = _require_page_auth(request)
    if redirect:
        return redirect
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    db = SessionLocal()
    try:
        edit_user = db.query(User).filter(User.id == edit_id).first()
        if not edit_user:
            raise HTTPException(status_code=404, detail="用户不存在")

        ctx = _template_context(request, user)
        ctx["edit_user"] = edit_user
        ctx["UserRole"] = UserRole
        ctx["UserStatus"] = UserStatus
        return templates.TemplateResponse("users/form.html", ctx)
    finally:
        db.close()


# ── Boot ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
