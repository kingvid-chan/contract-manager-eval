"""Tests for authentication: login, JWT, password validation."""


class TestLogin:
    """Login endpoint tests."""

    def test_login_success_admin(self, client, seed_users):
        """Admin can login with correct credentials."""
        r = client.post("/api/auth/login", data={
            "username": "admin", "password": "admin123"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"

    def test_login_success_manager(self, client, seed_users):
        """Manager can login."""
        r = client.post("/api/auth/login", data={
            "username": "manager", "password": "manager123"
        })
        assert r.status_code == 200

    def test_login_success_viewer(self, client, seed_users):
        """Viewer can login."""
        r = client.post("/api/auth/login", data={
            "username": "viewer", "password": "viewer123"
        })
        assert r.status_code == 200

    def test_login_wrong_password(self, client, seed_users):
        """Wrong password returns 401."""
        r = client.post("/api/auth/login", data={
            "username": "admin", "password": "wrong"
        })
        assert r.status_code == 401

    def test_login_wrong_username(self, client, seed_users):
        """Wrong username returns 401."""
        r = client.post("/api/auth/login", data={
            "username": "nonexistent", "password": "admin123"
        })
        assert r.status_code == 401

    def test_login_disabled_user(self, client, seed_users):
        """Disabled user cannot login."""
        r = client.post("/api/auth/login", data={
            "username": "disabled_user", "password": "disabled123"
        })
        assert r.status_code == 403

    def test_login_empty_fields(self, client):
        """Empty form returns 422."""
        r = client.post("/api/auth/login", data={})
        assert r.status_code == 422

    def test_token_contains_claims(self, client, seed_users):
        """JWT token contains sub and role claims."""
        r = client.post("/api/auth/login", data={
            "username": "admin", "password": "admin123"
        })
        token = r.json()["access_token"]
        from app.auth import decode_access_token
        payload = decode_access_token(token)
        assert payload is not None
        assert "sub" in payload
        assert payload["role"] == "admin"


class TestAuthGuard:
    """Tests for accessing protected endpoints without auth."""

    def test_unauthenticated_contracts(self, client):
        """Unauthenticated request to /api/contracts returns 401."""
        r = client.get("/api/contracts")
        assert r.status_code == 401

    def test_unauthenticated_users(self, client):
        """Unauthenticated request to /api/users returns 401."""
        r = client.get("/api/users")
        assert r.status_code == 401

    def test_invalid_token(self, client):
        """Invalid JWT token returns 401."""
        r = client.get("/api/contracts", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert r.status_code == 401
