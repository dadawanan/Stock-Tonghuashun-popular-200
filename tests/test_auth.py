"""认证模块集成测试。

需要运行中的 PostgreSQL 和 .env 配置。运行方式：
    pytest tests/test_auth.py -v
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from stock_service.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def registered_user(client: AsyncClient):
    """注册一个测试用户并返回凭据。"""
    resp = await client.post("/api/auth/register", json={"username": "testuser", "password": "test123456"})
    assert resp.status_code == 201
    data = resp.json()
    return {"username": "testuser", "password": "test123456", "id": data["data"]["id"]}


@pytest.fixture
async def logged_in_tokens(client: AsyncClient, registered_user):
    """登录并返回 token 对。"""
    resp = await client.post("/api/auth/login", json={
        "username": registered_user["username"],
        "password": registered_user["password"],
    })
    assert resp.status_code == 200
    return resp.json()["data"]


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/auth/register", json={"username": "newuser", "password": "pass123456"})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["username"] == "newuser"
        assert "id" in data

    async def test_register_duplicate_username(self, client: AsyncClient, registered_user):
        resp = await client.post("/api/auth/register", json={"username": "testuser", "password": "pass123456"})
        assert resp.status_code == 409

    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post("/api/auth/register", json={"username": "user2", "password": "123"})
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient, registered_user):
        resp = await client.post("/api/auth/login", json={
            "username": registered_user["username"],
            "password": registered_user["password"],
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, registered_user):
        resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "wrong"})
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post("/api/auth/login", json={"username": "nobody", "password": "pass"})
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_success(self, client: AsyncClient, logged_in_tokens):
        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": logged_in_tokens["refresh_token"],
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        # 新的 refresh token 应该不同于旧的
        assert data["refresh_token"] != logged_in_tokens["refresh_token"]

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post("/api/auth/refresh", json={"refresh_token": "invalid"})
        assert resp.status_code == 401

    async def test_refresh_reuse_old_token(self, client: AsyncClient, logged_in_tokens):
        """轮换后旧 token 应该失效。"""
        # 第一次刷新
        await client.post("/api/auth/refresh", json={"refresh_token": logged_in_tokens["refresh_token"]})
        # 用旧 token 再次刷新
        resp = await client.post("/api/auth/refresh", json={"refresh_token": logged_in_tokens["refresh_token"]})
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_success(self, client: AsyncClient, logged_in_tokens):
        headers = {"Authorization": f"Bearer {logged_in_tokens['access_token']}"}
        resp = await client.post("/api/auth/logout", json={
            "refresh_token": logged_in_tokens["refresh_token"],
        }, headers=headers)
        assert resp.status_code == 200

        # logout 后 refresh token 应该失效
        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": logged_in_tokens["refresh_token"],
        })
        assert resp.status_code == 401


class TestMe:
    async def test_me_success(self, client: AsyncClient, logged_in_tokens, registered_user):
        headers = {"Authorization": f"Bearer {logged_in_tokens['access_token']}"}
        resp = await client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == registered_user["username"]

    async def test_me_no_token(self, client: AsyncClient):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


class TestProtectedRoutes:
    async def test_popularity_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/popularity/fetch")
        assert resp.status_code == 401

    async def test_analysis_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/analyze")
        assert resp.status_code == 401

    async def test_health_is_public(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
