"""Tests for user management: CRUD operations and permissions."""


class TestUserList:
    """User list endpoint tests."""

    def test_admin_can_list_users(self, client, seed_users, auth_headers):
        """Admin can list all users."""
        r = client.get("/api/users", headers=auth_headers["admin"])
        assert r.status_code == 200
        users = r.json()
        assert len(users) >= 3

    def test_manager_cannot_list_users(self, client, seed_users, auth_headers):
        """Manager cannot access user list."""
        r = client.get("/api/users", headers=auth_headers["manager"])
        assert r.status_code == 403

    def test_viewer_cannot_list_users(self, client, seed_users, auth_headers):
        """Viewer cannot access user list."""
        r = client.get("/api/users", headers=auth_headers["viewer"])
        assert r.status_code == 403


class TestUserCreate:
    """User creation tests (admin only)."""

    def test_admin_can_create_user(self, client, seed_users, auth_headers):
        """Admin creates a new user successfully."""
        r = client.post("/api/users", json={
            "username": "newuser",
            "password": "newpass123",
            "display_name": "新用户",
            "email": "new@test.com",
            "role": "viewer",
            "status": "active",
        }, headers=auth_headers["admin"])
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "newuser"
        assert data["role"] == "viewer"

    def test_admin_create_duplicate_username(self, client, seed_users, auth_headers):
        """Cannot create user with duplicate username."""
        r = client.post("/api/users", json={
            "username": "admin",
            "password": "test123456",
            "display_name": "重复",
            "email": "dup@test.com",
            "role": "viewer",
            "status": "active",
        }, headers=auth_headers["admin"])
        assert r.status_code == 409

    def test_manager_cannot_create_user(self, client, seed_users, auth_headers):
        """Manager cannot create users."""
        r = client.post("/api/users", json={
            "username": "hack",
            "password": "hack123456",
            "display_name": "Hack",
            "email": "hack@test.com",
            "role": "admin",
            "status": "active",
        }, headers=auth_headers["manager"])
        assert r.status_code == 403

    def test_viewer_cannot_create_user(self, client, seed_users, auth_headers):
        """Viewer cannot create users."""
        r = client.post("/api/users", json={
            "username": "hack2",
            "password": "hack123456",
            "display_name": "Hack2",
            "email": "hack2@test.com",
            "role": "admin",
            "status": "active",
        }, headers=auth_headers["viewer"])
        assert r.status_code == 403


class TestUserUpdate:
    """User update tests (admin only)."""

    def test_admin_can_update_user(self, client, seed_users, auth_headers):
        """Admin updates user display_name and role."""
        user_id = seed_users["users"]["viewer"].id
        r = client.put(f"/api/users/{user_id}", json={
            "display_name": "改名字",
            "role": "manager",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200
        data = r.json()
        assert data["display_name"] == "改名字"
        assert data["role"] == "manager"

    def test_admin_can_change_password(self, client, seed_users, auth_headers):
        """Admin can reset a user's password."""
        user_id = seed_users["users"]["manager"].id
        r = client.put(f"/api/users/{user_id}", json={
            "password": "newpassword123",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200

        r2 = client.post("/api/auth/login", data={
            "username": "manager", "password": "newpassword123"
        })
        assert r2.status_code == 200

    def test_manager_cannot_update_user(self, client, seed_users, auth_headers):
        """Manager cannot update any user."""
        user_id = seed_users["users"]["viewer"].id
        r = client.put(f"/api/users/{user_id}", json={
            "display_name": "Hacked",
        }, headers=auth_headers["manager"])
        assert r.status_code == 403

    def test_update_nonexistent_user(self, client, seed_users, auth_headers):
        """Update nonexistent user returns 404."""
        r = client.put("/api/users/9999", json={
            "display_name": "Nobody",
        }, headers=auth_headers["admin"])
        assert r.status_code == 404
