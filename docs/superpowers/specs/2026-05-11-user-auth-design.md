# 用户认证模块设计

## 概述

为股票分析平台添加用户认证模块，支持多用户登录注册，使用 JWT 进行无状态认证，refresh token 存数据库支持主动撤销和轮换。

## 需求

- 注册：用户名 + 密码
- 登录：返回 access token + refresh token
- Access Token：30 分钟过期
- Refresh Token：7 天过期，存数据库，支持轮换
- 登出：单设备登出（删除当前 refresh token）
- 接口保护：所有现有 API 需要登录后才能访问
- 多用户系统

## 数据模型

### users 表

```sql
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(64) NOT NULL UNIQUE,
    password_hash   VARCHAR(128) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### refresh_tokens 表

```sql
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(128) NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
```

Refresh token 存 SHA256 哈希而非明文，数据库泄露时无法直接使用。

## API 接口

### POST /api/auth/register

注册新用户。

**Request:**
```json
{ "username": "alice", "password": "secret123" }
```

**Response 201:**
```json
{ "code": 0, "msg": "", "data": { "id": 1, "username": "alice" } }
```

**错误:**
- 409: 用户名已被注册
- 422: 用户名或密码格式不合法

### POST /api/auth/login

用户登录，返回 token 对。

**Request:**
```json
{ "username": "alice", "password": "secret123" }
```

**Response 200:**
```json
{
  "code": 0, "msg": "",
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g...",
    "token_type": "bearer"
  }
}
```

**错误:**
- 401: 用户名或密码错误

### POST /api/auth/refresh

用 refresh token 获取新的 access + refresh token（轮换）。

**Request:**
```json
{ "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g..." }
```

**Response 200:**
```json
{
  "code": 0, "msg": "",
  "data": {
    "access_token": "eyJ...(新的)",
    "refresh_token": "bmV3IHJlZnJlc2ggdG9rZW4...(新的)",
    "token_type": "bearer"
  }
}
```

**错误:**
- 401: refresh token 无效或已过期
- 401: refresh token 已失效（轮换检测，可能被盗用，清除该用户所有 token）

### POST /api/auth/logout

登出当前设备，删除对应的 refresh token。

**Request Header:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{ "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g..." }
```

**Response 200:**
```json
{ "code": 0, "msg": "", "data": null }
```

### GET /api/auth/me

获取当前登录用户信息。

**Request Header:**
```
Authorization: Bearer <access_token>
```

**Response 200:**
```json
{ "code": 0, "msg": "", "data": { "id": 1, "username": "alice" } }
```

## JWT 设计

**Payload:**
```json
{
  "sub": "1",
  "username": "alice",
  "type": "access",
  "exp": 1715400000,
  "iat": 1715398200
}
```

- 签名算法：HS256
- 密钥：从 `.env` 的 `JWT_SECRET_KEY` 读取，不硬编码
- Access Token 过期：30 分钟
- Refresh Token 过期：7 天

## 认证流程

```
1. 注册 → POST /api/auth/register → 无 token
2. 登录 → POST /api/auth/login → 返回 access + refresh
3. 访问 API → Header: Bearer <access_token>
4. access 过期 → POST /api/auth/refresh → 返回新 access + 新 refresh（旧 refresh 失效）
5. refresh 也过期 → 重新登录
6. 登出 → POST /api/auth/logout → 删除数据库中的 refresh token
```

## 接口保护

所有现有路由通过 FastAPI 依赖注入添加认证：

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = decode_access_token(token)
    user = await auth_crud.get_user_by_id(session, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="未授权")
    return user
```

现有路由只需添加 `current_user: dict = Depends(get_current_user)` 参数即可保护。

**例外：** `/api/health` 保持公开，不加认证（监控探测需要）。

## Refresh Token 轮换安全策略

1. 用户调用 /api/auth/refresh 时，传入旧 refresh token
2. 查数据库找到对应的 token_hash
3. 如果找到：删除旧记录，生成新的 access + refresh，存新 refresh token hash
4. 如果未找到（已被使用过）：说明可能被盗用，删除该用户所有 refresh token，返回 401
5. 定期清理过期的 refresh token（可选，后续添加）

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `api/routes/auth.py` | 认证路由（register/login/refresh/logout/me） |
| `application/services/auth_service.py` | 认证服务（密码哈希/JWT 签发验证/token 轮换） |
| `crud/auth_crud.py` | 用户和 refresh_token 的 CRUD |

### 修改文件

| 文件 | 改动 |
|------|------|
| `db/models/v2_models.py` | 追加 User + RefreshToken ORM 模型 |
| `schema_v2.sql` | 追加 users + refresh_tokens 表 |
| `api/app.py` | 注册 auth_router |
| `api/dependencies.py` | 新增 get_current_user + oauth2_scheme |
| `api/routes/popularity.py` | 添加 Depends(get_current_user) |
| `api/routes/analysis.py` | 添加 Depends(get_current_user) |
| `api/routes/query.py` | 添加 Depends(get_current_user) |
| `infrastructure/config/settings.py` | 追加 JWT 配置项 |
| `pyproject.toml` | 追加 passlib[bcrypt] + python-jose[cryptography] |

## 依赖

新增 Python 包：
- `passlib[bcrypt]` — 密码哈希
- `python-jose[cryptography]` — JWT 编解码

## 配置项

在 `settings.py` 和 `.env` 中新增：

```
JWT_SECRET_KEY=<随机生成的密钥>
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7
```

## 错误处理

| 场景 | HTTP 状态码 | 错误信息 |
|------|------------|---------|
| 用户名已存在 | 409 | "用户名已被注册" |
| 用户名或密码错误 | 401 | "用户名或密码错误" |
| access token 无效/过期 | 401 | "未授权" |
| refresh token 无效/过期 | 401 | "refresh token 无效或已过期" |
| refresh token 已被使用（轮换检测） | 401 | "refresh token 已失效，请重新登录" |
