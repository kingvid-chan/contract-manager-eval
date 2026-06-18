"""Tests for contract management endpoints."""

import pytest
from fastapi import status


class TestContractList:
    """GET /api/contracts — list contracts."""

    def test_list_all_contracts(self, client, auth_headers):
        """Any authenticated user should see all contracts."""
        r = client.get("/api/contracts", headers=auth_headers["admin"])
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_filter_by_status(self, client, auth_headers):
        """Filter contracts by status."""
        r = client.get("/api/contracts?status=draft", headers=auth_headers["admin"])
        assert r.status_code == 200
        for c in r.json():
            assert c["status"] == "draft"

    def test_search_by_keyword(self, client, auth_headers):
        """Search contracts by keyword in title."""
        r = client.get("/api/contracts?q=测试", headers=auth_headers["admin"])
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert any("测试" in c["title"] for c in data)

    def test_search_by_contract_no(self, client, auth_headers):
        """Search contracts by contract number prefix."""
        r = client.get("/api/contracts?q=HT-TEST-001", headers=auth_headers["admin"])
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["contract_no"] == "HT-TEST-001"

    def test_viewer_can_list_contracts(self, client, auth_headers):
        """Viewer should be able to list contracts."""
        r = client.get("/api/contracts", headers=auth_headers["viewer"])
        assert r.status_code == 200


class TestContractCreate:
    """POST /api/contracts — create contract."""

    def test_admin_can_create_contract(self, client, auth_headers):
        """Admin should be able to create a contract."""
        r = client.post("/api/contracts", json={
            "contract_no": "HT-2026-NEW",
            "title": "新测试合同",
            "party_a": "甲方",
            "party_b": "乙方",
            "amount": 50000.0,
            "start_date": "2026-02-01",
            "end_date": "2026-12-31",
        }, headers=auth_headers["admin"])
        assert r.status_code == 201
        data = r.json()
        assert data["contract_no"] == "HT-2026-NEW"
        assert data["status"] == "draft"

    def test_manager_can_create_contract(self, client, auth_headers):
        """Manager should be able to create a contract."""
        r = client.post("/api/contracts", json={
            "contract_no": "HT-2026-MGR",
            "title": "经理创建的合同",
            "party_a": "甲方",
            "party_b": "乙方",
        }, headers=auth_headers["manager"])
        assert r.status_code == 201

    def test_create_contract_duplicate_no(self, client, auth_headers):
        """Duplicate contract_no should return 409."""
        r = client.post("/api/contracts", json={
            "contract_no": "HT-TEST-001",
            "title": "重复合同",
            "party_a": "甲方",
            "party_b": "乙方",
        }, headers=auth_headers["admin"])
        assert r.status_code == 409

    def test_viewer_cannot_create_contract(self, client, auth_headers):
        """Viewer should get 403."""
        r = client.post("/api/contracts", json={
            "contract_no": "HT-2026-VIEWER",
            "title": "无权限合同",
            "party_a": "甲方",
            "party_b": "乙方",
        }, headers=auth_headers["viewer"])
        assert r.status_code == 403

    def test_create_contract_missing_fields(self, client, auth_headers):
        """Missing required fields should return 422."""
        r = client.post("/api/contracts", json={
            "contract_no": "HT-2026-BAD",
        }, headers=auth_headers["admin"])
        assert r.status_code == 422


class TestContractDetail:
    """GET /api/contracts/{id} — get contract detail."""

    def test_get_contract_detail(self, client, auth_headers):
        """Should return contract with attachments list."""
        r = client.get("/api/contracts", headers=auth_headers["admin"])
        contracts = r.json()
        contract_id = contracts[0]["id"]

        r = client.get(f"/api/contracts/{contract_id}", headers=auth_headers["admin"])
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == contract_id
        assert "attachments" in data

    def test_get_nonexistent_contract(self, client, auth_headers):
        """Non-existent contract should return 404."""
        r = client.get("/api/contracts/99999", headers=auth_headers["admin"])
        assert r.status_code == 404


class TestContractUpdate:
    """PUT /api/contracts/{id} — update contract."""

    def test_admin_can_update_contract(self, client, auth_headers):
        """Admin should be able to update title and description."""
        r = client.get("/api/contracts", headers=auth_headers["admin"])
        contract_id = r.json()[0]["id"]

        r = client.put(f"/api/contracts/{contract_id}", json={
            "title": "更新后的标题",
            "description": "新增备注内容",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "更新后的标题"

    def test_viewer_cannot_update_contract(self, client, auth_headers):
        """Viewer should get 403 when updating."""
        r = client.get("/api/contracts", headers=auth_headers["admin"])
        contract_id = r.json()[0]["id"]

        r = client.put(f"/api/contracts/{contract_id}", json={
            "title": "Hacked",
        }, headers=auth_headers["viewer"])
        assert r.status_code == 403

    def test_update_nonexistent_contract(self, client, auth_headers):
        """Updating non-existent contract should return 404."""
        r = client.put("/api/contracts/99999", json={
            "title": "Nobody",
        }, headers=auth_headers["admin"])
        assert r.status_code == 404


class TestContractDelete:
    """DELETE /api/contracts/{id} — delete contract."""

    def test_admin_can_delete_contract(self, client, auth_headers):
        """Admin should be able to delete a contract."""
        r = client.post("/api/contracts", json={
            "contract_no": "HT-2026-DEL",
            "title": "待删除合同",
            "party_a": "甲方",
            "party_b": "乙方",
        }, headers=auth_headers["admin"])
        assert r.status_code == 201
        contract_id = r.json()["id"]

        r = client.delete(f"/api/contracts/{contract_id}", headers=auth_headers["admin"])
        assert r.status_code == 204

        r = client.get(f"/api/contracts/{contract_id}", headers=auth_headers["admin"])
        assert r.status_code == 404

    def test_manager_cannot_delete_contract(self, client, auth_headers):
        """Manager should get 403 when deleting."""
        r = client.get("/api/contracts", headers=auth_headers["admin"])
        contract_id = r.json()[0]["id"]

        r = client.delete(f"/api/contracts/{contract_id}", headers=auth_headers["manager"])
        assert r.status_code == 403


class TestContractTransitions:
    """POST /api/contracts/{id}/transition — status transitions."""

    @pytest.fixture
    def draft_contract_id(self, client, auth_headers):
        """Create a fresh draft contract for transition tests."""
        r = client.post("/api/contracts", json={
            "contract_no": "HT-TRANS-TEST",
            "title": "状态流转测试",
            "party_a": "甲方",
            "party_b": "乙方",
        }, headers=auth_headers["admin"])
        assert r.status_code == 201
        return r.json()["id"]

    def test_draft_to_pending(self, client, auth_headers, draft_contract_id):
        """Draft → pending (submit)."""
        r = client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "pending",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_pending_to_signed(self, client, auth_headers, draft_contract_id):
        """Pending → signed (sign)."""
        client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "pending",
        }, headers=auth_headers["admin"])

        r = client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "signed",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200
        assert r.json()["status"] == "signed"

    def test_signed_to_terminated(self, client, auth_headers, draft_contract_id):
        """Signed → terminated (terminate)."""
        client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "pending",
        }, headers=auth_headers["admin"])
        client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "signed",
        }, headers=auth_headers["admin"])

        r = client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "terminated",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200
        assert r.json()["status"] == "terminated"

    def test_draft_direct_to_terminated(self, client, auth_headers, draft_contract_id):
        """Draft → terminated directly (withdraw)."""
        r = client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "terminated",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200
        assert r.json()["status"] == "terminated"

    def test_pending_return_to_draft(self, client, auth_headers, draft_contract_id):
        """Pending → draft (return)."""
        client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "pending",
        }, headers=auth_headers["admin"])

        r = client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "draft",
        }, headers=auth_headers["admin"])
        assert r.status_code == 200
        assert r.json()["status"] == "draft"

    def test_invalid_transition(self, client, auth_headers, draft_contract_id):
        """Cannot go draft → expired (not a valid edge)."""
        r = client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "expired",
        }, headers=auth_headers["admin"])
        assert r.status_code == 400

    def test_invalid_action_name(self, client, auth_headers, draft_contract_id):
        """Bad action name should return 400."""
        r = client.post(f"/api/contracts/{draft_contract_id}/transition", json={
            "action": "invalid_action",
        }, headers=auth_headers["admin"])
        assert r.status_code == 400

    def test_viewer_cannot_transition(self, client, auth_headers):
        """Viewer should get 403."""
        r = client.get("/api/contracts", headers=auth_headers["admin"])
        contract_id = r.json()[0]["id"]

        r = client.post(f"/api/contracts/{contract_id}/transition", json={
            "action": "pending",
        }, headers=auth_headers["viewer"])
        assert r.status_code == 403


class TestSSRContractPages:
    """SSR page tests for contracts."""

    def test_contracts_page_requires_auth(self, client):
        """Contracts page redirects to login when unauthenticated."""
        r = client.get("/projects/contract-manager-eval/contracts", follow_redirects=False)
        assert r.status_code in (302, 307)

    def test_contracts_page_authenticated(self, client, auth_cookies):
        """Authenticated user sees contracts page with no-cache."""
        r = client.get("/projects/contract-manager-eval/contracts", cookies=auth_cookies["admin"])
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert r.headers["cache-control"] == "no-cache"

    def test_contract_detail_page(self, client, auth_headers, auth_cookies):
        """Contract detail page renders for authenticated user."""
        r = client.get("/api/contracts", headers=auth_headers["admin"])
        contract_id = r.json()[0]["id"]

        r = client.get(f"/projects/contract-manager-eval/contracts/{contract_id}",
                       cookies=auth_cookies["admin"])
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_new_contract_page(self, client, auth_cookies):
        """New contract page renders for admin."""
        r = client.get("/projects/contract-manager-eval/contracts/new",
                       cookies=auth_cookies["admin"])
        assert r.status_code == 200

    def test_new_contract_page_viewer_forbidden(self, client, auth_cookies):
        """New contract page forbids viewer."""
        r = client.get("/projects/contract-manager-eval/contracts/new",
                       cookies=auth_cookies["viewer"])
        assert r.status_code == 403
