# ADR 001: 测试 Fixtures 设计 — 内存 SQLite + StaticPool + Function 级隔离

## 日期

2026-06-18

## 状态

已采纳

## 上下文

合同管理系统 MVP（0.0.1）使用 pytest + FastAPI TestClient 作为测试框架，需要为 69 个测试用例提供可靠、快速且相互隔离的数据库环境。选型需满足以下约束：

1. **隔离性**：每个测试函数的数据库状态不互相影响
2. **速度**：测试套件应在数秒内完成，避免磁盘 I/O 成为瓶颈
3. **可重复性**：测试结果不依赖外部文件或服务
4. **简单性**：无需安装额外依赖（如 Docker、测试用 PostgreSQL）

## 决策

### 1. SQLite 内存数据库 (`sqlite://`)

使用 `sqlite://`（内存模式）替代文件模式或 PostgreSQL：

```python
TEST_ENGINE = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
```

- **不是文件模式**：避免磁盘 I/O、残留清理问题、并发文件锁冲突
- **不是 PostgreSQL**：部署复杂度高，MVP 已选用 SQLite 作为生产数据库，测试与生产保持一致

### 2. StaticPool 连接复用

使用 SQLAlchemy 的 `StaticPool` 而非默认的 `QueuePool` 或 `NullPool`：

- **StaticPool 保证所有连接共享同一个 DBAPI 连接**，从而访问同一个内存 SQLite 实例
- 如果使用 `NullPool`，每次 `create_all()`/`drop_all()` 在不同连接上操作，导致表不可见
- 如果使用 `QueuePool`，连接池中的不同连接可能指向不同的内存数据库实例

`connect_args={"check_same_thread": False}` 允许跨线程使用同一连接，满足 FastAPI TestClient 的线程模型。

### 3. Function 级 scope + `autouse=True` 隔离

```python
@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=TEST_ENGINE)   # 清理上一测试残留
    Base.metadata.create_all(bind=TEST_ENGINE)  # 建表
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)   # 拆除
```

- **`autouse=True`**：每个测试函数自动触发，无需显式声明依赖
- **`function` scope（默认）**：每个测试函数获得全新的表结构，消除测试间状态泄漏
- **不是 session 级**：如果多个测试共享 session，前一个测试的脏数据可能影响后续断言
- **不是 module 级**：跨测试函数的约束冲突（如 unique 用户名）无法处理
- **teardown 执行 `drop_all`**：确保当前测试的残留数据不影响后续测试，即使测试本身失败

### 4. 依赖注入覆盖

```python
@pytest.fixture
def client():
    from app.main import app

    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()  # 清理覆盖
```

- FastAPI 的 `dependency_overrides` 机制将生产环境的 `get_db` 替换为测试 Session
- Fixture teardown 清理覆盖，防止跨 fixtre 泄漏

### 5. 环境变量覆盖

```python
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
os.environ["UPLOAD_DIR"] = "data/test_uploads"
```

- 在导入应用模块之前设置，确保 `app.config` 读取测试专用配置
- 测试密钥硬编码但不可用于生产，避免误用

### 6. Fixture 依赖链

```
setup_test_db (autouse, function)  ← 所有测试的数据库基础
    ↓
db (function)                       ← 提供独立 session，commit/rollback 封装
    ↓
seed_users (function)               ← 插入种子用户和合同，返回 credentials
    ↓
auth_headers / auth_cookies         ← 调用 POST /api/auth/login 获取各角色 token
```

## 考虑过的替代方案

### A. 文件模式 SQLite (`sqlite:///:memory:` 替代为文件路径)

**不采纳理由**：
- 需要清理临时文件，复杂化 teardown
- 文件 I/O 比内存慢
- WAL 模式下残留 `-wal`/`-shm` 文件可能污染测试环境

### B. pytest-sqlalchemy 插件的事务回滚隔离

**不采纳理由**：
- 增加额外依赖
- 事务回滚模式与 FastAPI `dependency_overrides` 的 session 生命周期不兼容
- 部分场景需要真实 commit 行为（如测试审计日志的 flush 时序）

### C. 数据库事务嵌套（SAVEPOINT 回滚）

**不采纳理由**：
- SQLite 对 SAVEPOINT 支持有限
- autouse create/drop 更直观，出问题时更容易调试
- FastAPI TestClient 多线程模型下 SAVEPOINT 事务管理复杂

### D. Module 级 scope

**不采纳理由**：
- 测试间存在 unique 约束冲突（如用户名重复插入 403 测试）
- 某些测试场景需要特定数据库状态（如 disabled 用户、特定合同状态组合）
- function 级虽然略慢，但 69 个测试仍在 2 秒内完成

## 影响

- 测试完全自包含，无需任何外部服务或文件
- 可在 CI 环境中零配置运行
- 新增测试用例自动继承隔离保证，无需额外设置
- `conftest.py` 作为所有测试的单一 fixture 入口，降低维护成本

## 关联

- [ADR 002: Python FastAPI + SQLite 技术选型](01-python-fastapi-sqlite.md)（待创建）
- [ADR 003: Jinja2 SSR 前端方案](02-jinja2-ssr.md)（待创建）
- 迭代文档：[docs/iterations/0.0.1.md](../iterations/0.0.1.md)
- 测试策略文档：[docs/architecture.md](../architecture.md) §测试策略
