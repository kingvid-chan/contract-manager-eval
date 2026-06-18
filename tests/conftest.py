"""Pytest fixtures for the contract manager test suite."""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override settings before importing app modules
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = "sqlite:///./data/test_contract_manager.db"
os.environ["UPLOAD_DIR"] = "data/test_uploads"

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import User, Contract, ContractStatus, UserRole, UserStatus
from app.auth import hash_password


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create test database tables before each test module, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    # Clean up
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Provide a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI TestClient."""
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seed_users(db):
    """Create demo users and return their credentials."""
    users_data = [
        {"username": "admin", "password": "admin123", "display_name": "管理员",
         "email": "admin@test.com", "role": UserRole.admin, "status": UserStatus.active},
        {"username": "manager", "password": "manager123", "display_name": "经理",
         "email": "manager@test.com", "role": UserRole.manager, "status": UserStatus.active},
        {"username": "viewer", "password": "viewer123", "display_name": "只读",
         "email": "viewer@test.com", "role": UserRole.viewer, "status": UserStatus.active},
        {"username": "disabled_user", "password": "disabled123", "display_name": "已禁用",
         "email": "disabled@test.com", "role": UserRole.viewer, "status": UserStatus.disabled},
    ]

    users = {}
    for u in users_data:
        user = User(
            username=u["username"],
            password_hash=hash_password(u["password"]),
            display_name=u["display_name"],
            email=u["email"],
            role=u["role"],
            status=u["status"],
        )
        db.add(user)
        db.flush()
        users[u["username"]] = user

    # Create sample contracts
    for i in range(3):
        contract = Contract(
            contract_no=f"HT-TEST-00{i+1}",
            title=f"测试合同 {i+1}",
            party_a="甲方公司",
            party_b="乙方公司",
            amount=10000.0 * (i + 1),
            status=ContractStatus.draft,
            created_by=users["admin"].id,
        )
        db.add(contract)

    db.commit()

    # Refresh users to get IDs
    for u in users.values():
        db.refresh(u)

    return {
        "users": users,
        "credentials": {
            "admin": ("admin", "admin123"),
            "manager": ("manager", "manager123"),
            "viewer": ("viewer", "viewer123"),
            "disabled": ("disabled_user", "disabled123"),
        },
    }


@pytest.fixture
def auth_headers(client, seed_users):
    """Return auth headers for each role."""
    tokens = {}
    for role in ("admin", "manager", "viewer"):
        username, password = seed_users["credentials"][role]
        r = client.post("/api/auth/login", data={"username": username, "password": password})
        assert r.status_code == 200, f"Failed to login as {role}: {r.text}"
        tokens[role] = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return tokens


@pytest.fixture
def auth_cookies(client, seed_users):
    """Return auth cookies for SSR page access."""
    cookies = {}
    for role in ("admin", "manager", "viewer"):
        username, password = seed_users["credentials"][role]
        r = client.post("/api/auth/login", data={"username": username, "password": password})
        token = r.json()["access_token"]
        cookies[role] = {"access_token": token}
    return cookies
