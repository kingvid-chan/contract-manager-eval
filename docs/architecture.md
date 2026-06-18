# 合同管理系统 当前架构

## 系统目标与边界

合同管理系统（Contract Manager）是一个面向中小企业合同全生命周期管理的 Web 应用，MVP（0.0.1）覆盖以下核心能力：

- **认证与授权**：用户名+密码登录，JWT Bearer Token / Cookie 双通道认证，基于角色的访问控制（admin / manager / viewer）
- **合同管理**：合同 CRUD、状态流转（草稿→待签→已签→终止/过期）、关键词搜索与状态筛选
- **附件管理**：上传/下载/删除，基于扩展名 + magic bytes 的双重文件类型校验，10MB 大小限制
- **用户管理**：admin 角色可创建/编辑/启禁用用户
- **操作审计**：所有 CUD 操作记录审计日志

**不在范围内**：邮件通知、电子签章集成、多租户、国际化、移动端适配、SSO/OAuth。

## 技术栈与选择理由

| 组件 | 选型 | 理由 |
|------|------|------|
| 后端框架 | FastAPI 0.104+ | 异步支持、自动 OpenAPI 文档、类型安全、高性能 |
| ORM | SQLAlchemy 2.0+ | 成熟稳定、声明式映射、session 管理完善 |
| 数据库 | SQLite (WAL 模式) | 零配置、文件级部署、适合演示和小规模使用 |
| 认证 | PyJWT + bcrypt | 无状态 JWT 适合 API + SSR 混合场景；bcrypt 为密码哈希行业标准 |
| 模板引擎 | Jinja2 (独立使用) | FastAPI 原生支持、SSR 无前端构建工具链 |
| 前端 | 纯 HTML/CSS/JS | 无 SPA 框架依赖、零构建步骤、符合演示项目定位 |
| 测试 | pytest + httpx | FastAPI 官方推荐、TestClient 支持完整请求模拟 |

**为什么不选择**：
- **Django**：过重，ORM 与模板耦合度高，不适合以 API 为中心的设计
- **PostgreSQL**：增加部署复杂度，演示场景不需要
- **React/Vue SPA**：增加前端构建工具链，与 Jinja2 SSR 定位冲突

详见 ADR：[01-python-fastapi-sqlite](decisions/01-python-fastapi-sqlite.md)、[02-jinja2-ssr](decisions/02-jinja2-ssr.md)

## 模块职责与依赖

```
app/
├── config.py          # 环境变量读取（JWT_SECRET, DATABASE_URL, BASE_PATH 等）
├── database.py        # SQLAlchemy engine + SessionLocal + Base + get_db 依赖
├── models.py          # ORM 模型：User, Contract, Attachment, AuditLog
├── schemas.py         # Pydantic 请求/响应模型
├── auth.py            # bcrypt 哈希 + JWT 签发/验证
├── dependencies.py    # FastAPI 依赖注入：get_current_user, require_admin, require_manager_or_admin
├── middleware.py       # CacheControlMiddleware：HTML 响应添加 Cache-Control: no-cache
├── utils.py           # 附件校验（magic bytes）、存储路径生成、审计日志辅助
├── main.py            # FastAPI 应用组装 + Jinja2 环境 + SSR 页面路由 + StaticFiles 挂载
└── routers/
    ├── auth.py        # POST /api/auth/login
    ├── users.py       # CRUD /api/users（admin only）
    ├── contracts.py   # CRUD /api/contracts + 状态流转 + 筛选搜索
    └── attachments.py # POST/GET/DELETE /api/contracts/{id}/attachments
```

**依赖方向**：`routers` → `schemas` + `models` + `dependencies` → `auth` + `database` → `config`

`main.py` 作为组装根，导入所有路由器和中间件，额外负责 Jinja2 模板渲染和 SSR 路由。

## 数据流、状态流与外部接口

### 认证流

1. 客户端 POST `/api/auth/login` 发送 username + password
2. 服务端 bcrypt 验证密码 → 创建 JWT（含 sub=user_id, role, exp=8h）
3. 响应返回 JSON（含 access_token）+ Set-Cookie（access_token）
4. 后续请求：API 端从 `Authorization: Bearer <token>` 取，SSR 端从 Cookie 取
5. dependencies.py 的 `get_current_user` 解析 JWT → 查询 User → 验证状态

### 合同状态机

```
draft ──→ pending ──→ signed ──→ terminated
  │          │                      ↑
  │          └──→ draft (退回)       │
  └──────────→ terminated (撤回)    │
                         expired ──→ (自动，end_date < now)
```

- `draft → pending`：提交审批
- `pending → signed`：签署（自动设置 sign_date）
- `signed → terminated`：终止
- `signed → expired`：自动（查询时判断 end_date < utcnow）
- `draft → terminated`：撤回
- `pending → draft`：退回

状态流转校验在 `app/routers/contracts.py` 的 `VALID_TRANSITIONS` 字典中定义。

### 附件上传流

1. 客户端选择文件（前端校验扩展名 .pdf/.doc/.docx）
2. `POST /api/contracts/{id}/attachments` multipart/form-data
3. 服务端读取文件内容 → `validate_attachment()` 校验扩展名 + magic bytes + ≤10MB
4. 生成存储路径 `uploads/{contract_id}/{uuid12}_{original_name}`
5. 写入文件系统 + 创建 Attachment 数据库记录 + 记录审计日志

### 权限矩阵

| 操作 | admin | manager | viewer |
|------|-------|---------|--------|
| 登录 | ✓ | ✓ | ✓ |
| 合同列表/详情 | ✓ | ✓ | ✓ |
| 合同创建/编辑 | ✓ | ✓ | ✗ |
| 合同删除 | ✓ | ✗ | ✗ |
| 合同状态流转 | ✓ | ✓ | ✗ |
| 附件上传/删除 | ✓ | ✓ | ✗ |
| 附件下载 | ✓ | ✓ | ✓ |
| 用户管理 CRUD | ✓ | ✗ | ✗ |

## 测试策略

- **框架**：pytest + FastAPI TestClient (httpx)
- **数据库隔离**：SQLite 内存数据库 + StaticPool 连接复用，函数级 create_all/drop_all
- **数据隔离**：每个测试函数独立建表、种子数据、拆除，`seed_users` fixture 通过事务隔离确保无泄漏
- **代码复用**：`conftest.py` 提供 db、client、seed_users、auth_headers、auth_cookies 共享 fixture
- **覆盖范围**：69 个测试用例覆盖认证、用户 CRUD、合同 CRUD、状态流转、附件上传/下载/删除、SSR 页面、权限控制
- **测试命令**：`python -m pytest tests/ -v`

## 部署拓扑

```
用户浏览器
  │
  ▼
Nginx (120.24.117.67)
  │ location /projects/contract-manager-eval/
  │   proxy_pass → FastAPI (127.0.0.1:8000)
  │
  ▼
FastAPI (uvicorn)
  ├── StaticFiles mounted at /projects/contract-manager-eval/static/
  ├── API routes: /api/*
  └── SSR routes: /projects/contract-manager-eval/*
```

- 静态资源：由 FastAPI `StaticFiles` 中间件直接提供，路径前缀 `/projects/contract-manager-eval/static/`
- 上传文件：存储在服务器 `uploads/` 目录，由 API 路由提供下载
- 数据库：SQLite 文件 `data/contract_manager.db`

## 安全边界

- **密码存储**：bcrypt（salt rounds 自动），数据库不存明文
- **Token**：JWT HS256 签名，8 小时过期，Secret 通过环境变量注入不入库
- **文件上传**：扩展名白名单 + magic bytes 双重校验，防止伪装类型；10MB 上限防 DoS
- **SQL 注入**：SQLAlchemy ORM 参数化查询
- **XSS**：Jinja2 默认自动转义 HTML
- **CSRF**：演示项目未实施 CSRF token（MVP 范围外，生产需加）
- **CORS**：未启用（同源部署）
- **审计**：所有 CUD 操作记录 AuditLog（操作人、类型、实体 ID、详情）

## 已知技术债

| 项目 | 影响 | 缓解 |
|------|------|------|
| SQLite 并发写锁 | 多用户同时写入可能阻塞 | WAL 模式；演示场景并发低 |
| 无 CSRF 保护 | Cookie 认证存在 CSRF 风险 | MVP 范围外；生产需加 SameSite Cookie + CSRF token |
| 无速率限制 | 登录接口可能被暴力破解 | 演示账号，密码已知；生产需加 |
| 附件无去重 | 同名文件重复上传浪费存储 | 路径含 uuid 前缀防覆盖 |
| `datetime.utcnow()` 废弃 | Python 3.12+ 废弃警告 | 需迁移至 `datetime.now(datetime.UTC)` |
| 测试 cookie 方式废弃 | Starlette 新版废弃 per-request cookies | 需迁移至 client.cookies 设置 |

## 关联 ADR 与最近变更

- [ADR 01: Python FastAPI + SQLite 技术选型](decisions/01-python-fastapi-sqlite.md)
- [ADR 02: Jinja2 SSR 前端方案](decisions/02-jinja2-ssr.md)
- 迭代文档：[docs/iterations/0.0.1.md](iterations/0.0.1.md)
- 运行手册：[docs/runbook.md](runbook.md)
