# 合同管理系统 运行手册

## 本地安装与启动

### 环境要求

- Python 3.10+
- pip

### 安装步骤

```bash
# 1. 克隆项目 / 进入项目目录
cd contract-manager-eval

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 修改 JWT_SECRET 等敏感值（可选，默认值可用于本地开发）

# 5. 初始化数据库
python scripts/init_db.py
# 输出: Creating database tables... Tables created. Seeding demo data...
#        Created user: admin (role=admin)
#        Created user: manager (role=manager)
#        Created user: viewer (role=viewer)
#        Created contract: HT-2026-001 (status=signed)
#        ...

# 6. 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# 或直接运行: python app/main.py
```

### 访问地址

- 本地首页：http://localhost:8000/projects/contract-manager-eval/contracts
- 登录页：http://localhost:8000/projects/contract-manager-eval/login
- API 文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/healthz

## 测试、构建与健康检查

### 运行测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_auth.py -v

# 带覆盖率
pip install pytest-cov
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

### 健康检查

```bash
# 健康检查端点
curl http://localhost:8000/healthz
# 预期响应: {"status":"ok","version":"0.0.1"}

# API 登录测试
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=admin123"
# 预期响应: {"access_token":"...","token_type":"bearer","user":{...}}
```

### 公网浏览器验收关键流程

1. 访问 `http://120.24.117.67/projects/contract-manager-eval/login`
2. 使用演示账号 `admin / admin123` 登录
3. 验证合同列表页加载、状态下拉筛选、关键词搜索
4. 验证合同详情页 + 附件上传下载
5. 验证用户管理页（admin 可见）
6. 验证退出登录后重定向到登录页

**静态资源检查**：
- 所有 CSS/JS 请求 URL 须带 `?v=0.0.1` 版本令牌
- 路径前缀为 `/projects/contract-manager-eval/static/`
- 状态码 200–399

**响应头检查**：
- 所有 HTML 文档响应头须含 `Cache-Control: no-cache`
- 由服务端 Middleware 下发，非 `<meta>` 标签

**视觉审查**：
- 由 Kimi 视觉模型自动执行截图对比

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `JWT_SECRET` | JWT 签名密钥 | `change-me-in-production-use-random-string` |
| `JWT_ALGORITHM` | JWT 签名算法 | `HS256` |
| `JWT_EXPIRE_HOURS` | Token 有效期（小时） | `8` |
| `DATABASE_URL` | SQLite 数据库路径 | `sqlite:///./data/contract_manager.db` |
| `UPLOAD_DIR` | 附件存储目录 | `uploads` |
| `MAX_UPLOAD_SIZE` | 上传文件大小上限（字节） | `10485760` (10MB) |
| `BASE_PATH` | 部署路径前缀 | `/projects/contract-manager-eval` |

## Base Path

项目必须支持 `/projects/contract-manager-eval/`，静态资源和前端路由不得假设部署在 `/`。

### 代码中的 Base Path 处理

- **SSR 页面路由**：`main.py` 中所有页面路由以 `f"{settings.BASE_PATH}/..."` 为前缀
- **模板 URL**：所有链接、表单 action、资源引用使用 `{{ base_path }}/...` 模板变量
- **前端 JS**：`BASE_PATH` 从 `<body data-base-path="...">` 读取并暴露为 `window.BASE_PATH`
- **API 路由**：使用相对路径 `/api/...`（Nginx 代理）
- **静态文件**：通过 `app.mount(f"{settings.BASE_PATH}/static", ...)` 挂载

公网浏览器验收时，最终 URL 和所有项目资源必须保留此前缀。

## 缓存策略

功能迭代后公网 URL 不变，必须防止浏览器缓存命中旧页面：

- **HTML 文档**：真实 **HTTP 响应头**必须携带 `Cache-Control: no-cache`（或 `no-store`），每次重新校验。**不得仅用 `<meta http-equiv>` 标签**（浏览器基本忽略其缓存语义）。由服务器/框架下发响应头（`app/middleware.py` 的 `CacheControlMiddleware`）。
- **静态资源**：所有静态资源 URL 必须携带版本令牌 `?v=<当前发布版本 0.0.N>`，且路径保留 `/projects/contract-manager-eval/` 前缀（令牌挂在已带 basePath 的 URL 上）。
- **版本令牌**：随 `0.0.N` 递增，每个交付版本自动触发缓存失效。

浏览器验收（schema v3 机器报告）会逐条重算：`static_assets` 状态码 200–399、URL 带版本令牌且在 basePath 下（自包含页面可为空），`document_response_headers` 的真实 `Cache-Control` 为 no-cache/no-store，视觉审查须由 Kimi 视觉模型完成。

## Aliyun systemd 与 Nginx

### Nginx 配置要点

```nginx
location /projects/contract-manager-eval/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### systemd 服务

```ini
[Unit]
Description=Contract Manager Eval
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/contract-manager-eval
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/path/to/contract-manager-eval/.env

[Install]
WantedBy=multi-user.target
```

## 日志查看

```bash
# uvicorn 日志
journalctl -u contract-manager-eval -f

# 应用日志（如配置了文件日志）
tail -f logs/app.log
```

## 常见故障与恢复

| 故障 | 现象 | 解决 |
|------|------|------|
| 数据库锁定 | 写入操作超时 | SQLite WAL 模式已启用；避免并发写入 |
| 静态资源 404 | CSS/JS 加载失败 | 检查 `BASE_PATH` 环境变量与 Nginx location 一致 |
| 登录失败 | 密码错误 | 重新运行 `scripts/init_db.py` 重置演示账号 |
| 附件上传失败 | 400 错误 | 检查文件类型（仅 .pdf/.doc/.docx）和大小（≤10MB） |
| Token 过期 | 401 Unauthorized | 重新登录获取新 Token（8 小时有效期） |
| 端口占用 | 启动失败 | `lsof -i :8000` 查找并终止占用进程 |

## 回滚到精确 Tag

```bash
# 当前迭代不创建 tag（按 CLAUDE.md 约束）
# 回滚通过 git checkout 到目标 commit
git log --oneline  # 查看提交历史
git checkout <commit-hash>
```
