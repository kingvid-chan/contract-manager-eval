# ADR 01: Python FastAPI + SQLite 技术选型

**状态**：已采用  
**日期**：2026-06-18  
**决策者**：技术专家 (Claude)

## 背景

合同管理系统 MVP (0.0.1) 需要选择后端技术栈。核心需求：

1. RESTful API + 服务端渲染（SSR）混合模式
2. 演示项目，部署在单台阿里云 ECS
3. 无需专业 DBA 运维
4. 快速迭代，零外部依赖（不依赖 Redis、消息队列等中间件）

## 决策

**采用 Python FastAPI + SQLAlchemy + SQLite 作为后端技术栈**。

具体选型：
- **Web 框架**：FastAPI 0.104+
- **ORM**：SQLAlchemy 2.0+
- **数据库**：SQLite（WAL 模式）
- **部署**：uvicorn ASGI server

## 理由

### FastAPI 而非 Django / Flask

| 维度 | FastAPI | Django | Flask |
|------|---------|--------|-------|
| API 优先设计 | ✓ 原生支持 | 需 DRF 扩展 | 需扩展 |
| 自动文档 | OpenAPI/Swagger 内置 | 需 drf-spectacular | 需扩展 |
| 类型安全 | Pydantic 集成 | 需额外配置 | 无 |
| 异步支持 | 原生 async/await | 3.1+ 有限支持 | 需扩展 |
| 学习曲线 | 低（API 优先理念清晰） | 中（全套需理解） | 低 |
| 项目规模匹配 | MVP 轻量 | 过重 | 可接受 |

**选择 FastAPI 的关键理由**：
1. Pydantic 模型提供请求/响应自动校验和序列化，减少样板代码
2. 依赖注入系统（Depends）天然适合认证中间件模式
3. 自动 OpenAPI 文档降低前后端协作成本
4. async 支持为未来扩展留有余地

### SQLite 而非 PostgreSQL

| 维度 | SQLite | PostgreSQL |
|------|--------|------------|
| 部署复杂度 | 零配置，文件即数据库 | 需安装、配置、管理 |
| 运维成本 | 无 | 需备份策略、连接池管理 |
| 并发能力 | 单写者（WAL 模式改善） | 高并发读写 |
| 数据量级 | GB 级单文件 | TB 级 |
| 演示适配 | ✓ 完美 | 过重 |

**选择 SQLite 的关键理由**：
1. 演示项目 3-5 个并发用户，SQLite WAL 模式完全够用
2. 单文件部署，`.env` + `data/contract_manager.db` 即可迁移
3. `init_db.py` 一键初始化，无需单独的数据库服务
4. 若未来需迁移至 PostgreSQL，SQLAlchemy ORM 层提供抽象保护（仅需改连接串）

## 替代方案

### 方案 B：Django + DRF + PostgreSQL
- **优点**：admin 后台开箱即用、生态成熟
- **缺点**：项目定位为 API + SSR 混合，Django 的全栈约定与架构设计冲突；PostgreSQL 运维负担不符合演示定位
- **弃用原因**：过重，不符合 MVP 轻量理念

### 方案 C：Node.js Express + MongoDB
- **优点**：全栈 JavaScript、JSON 原生支持
- **缺点**：MongoDB 非关系型不适合合同管理的强 schema 场景；团队技术栈偏好 Python
- **弃用原因**：关系型数据不适合文档数据库

## 影响与限制

### 已知限制

1. **SQLite 单写者锁**：多用户同时执行 CUD 操作时可能遇到 `database is locked` 错误
   - 缓解：WAL 模式（已启用），读不阻塞写
   - 演示场景 3-5 用户，实际触发概率低

2. **SQLite 类型系统宽松**：不强制列类型，需 ORM 层 + Pydantic 双重校验
   - 缓解：SQLAlchemy 列类型定义 + Pydantic schema 校验

3. **无连接池**：SQLite 为嵌入式数据库，连接池意义不大
   - 缓解：SQLAlchemy `NullPool` + `check_same_thread=False`

## 相关 ADR

- [ADR 02: Jinja2 SSR 前端方案](02-jinja2-ssr.md)
