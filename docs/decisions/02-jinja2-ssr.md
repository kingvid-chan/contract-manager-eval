# ADR 02: Jinja2 SSR 前端方案

**状态**：已采用  
**日期**：2026-06-18  
**决策者**：技术专家 (Claude)

## 背景

合同管理系统需要在浏览器端提供完整的交互体验，包括：

1. 合同列表展示（服务端分状态筛选、关键词搜索）
2. 合同详情 + 附件管理
3. 用户管理界面
4. 表单提交（合同创建/编辑、用户管理）
5. 状态流转操作

需要决定前端架构方案，平衡开发效率、用户体验和部署复杂度。

## 决策

**采用 Jinja2 服务端渲染（SSR）+ 纯 JavaScript 渐进增强**。

架构分工：
- **页面骨架**：Jinja2 渲染 HTML，服务端直接输出完整页面
- **交互增强**：纯 JavaScript（无框架）处理表单 AJAX 提交、文件上传、状态流转等
- **样式**：手写 CSS 变量驱动的企业后台风格

## 理由

### vs React/Vue SPA

| 维度 | Jinja2 SSR + Vanilla JS | React/Vue SPA |
|------|------------------------|---------------|
| 构建工具链 | 无（零构建步骤） | webpack/vite、babel、npm |
| 首屏加载 | 服务端直接输出 HTML，即时渲染 | 需加载 JS bundle + API 调用 |
| 开发复杂度 | 低（模板 + 内联脚本） | 中高（状态管理、路由、组件化） |
| SEO | 天然支持 | 需 SSR 框架（Next.js/Nuxt） |
| 前后端分离 | 弱（模板耦合后端） | 强 |
| 部署 | 单服务 | 通常需静态资源 CDN |

**选择 Jinja2 SSR 的关键理由**：

1. **零构建工具链**：`python app/main.py` 即可启动完整应用，无需 npm install / webpack build
2. **首屏性能**：服务端直接渲染 HTML，浏览器无白屏等待
3. **开发效率**：模板直接访问后端上下文（用户角色、合同状态枚举等），无需额外的 API 调用层
4. **部署简单**：单进程服务，无需静态资源独立部署
5. **匹配项目规模**：MVP 约 10 个页面，SPA 框架在此规模下是过度工程

### vs htmx

| 维度 | Jinja2 SSR | htmx |
|------|-----------|------|
| 引入方式 | 内置（Python 生态） | 需引入 JS 库 |
| 成熟度 | 极成熟（15+ 年） | 较新 |
| 社区 | 极广泛 | 增长中 |
| 学习成本 | 模板语法简单 | HX 属性需学习 |

**选择 Jinja2 而非 htmx 的理由**：
1. htmx 虽理念契合但引入额外依赖，MVP 倾向于最小化依赖
2. Jinja2 模板语法团队更熟悉
3. 表单 AJAX 提交等增强功能用 ~200 行 JS 即可覆盖

## 版本令牌策略

按 CLAUDE.md 约束：所有静态资源 URL 必须带 `?v=<当前 0.0.N>` 版本令牌。

### 实现

1. **模板层**：`<link href="{{ base_path }}/static/css/style.css?v={{ version }}">`
2. **JS 层**：`BASE_PATH` 和 `VERSION` 从 `<body data-base-path="..." data-version="...">` 读取
3. **版本号**：在 `main.py` 中硬编码 `VERSION = "0.0.1"`，每次迭代递增

### 缓存策略配合

- **HTML 文档**：`Cache-Control: no-cache`（由 `CacheControlMiddleware` 下发真实 HTTP 响应头）
- **静态资源**：版本令牌 + 长缓存（浏览器默认行为）—— 版本号变化自动触发重新下载
- **严禁**：使用 `<meta http-equiv>` 标签代替真实 HTTP 响应头（浏览器基本忽略其缓存语义）

## 替代方案

### 方案 B：React SPA (Create React App / Vite)

- **优点**：组件化、状态管理成熟、生态系统丰富
- **缺点**：需要 npm 工具链、构建步骤、首屏加载慢、需额外 API 调用层
- **弃用原因**：MVP 规模下过度工程；构建工具链增加运维复杂度

### 方案 C：htmx + Jinja2 Template Fragments

- **优点**：保持 SSR 模式同时实现 SPA-like 交互
- **缺点**：引入额外 JS 依赖；htmx 生态相对较新
- **弃用原因**：MVP 所需的交互强度（表单 AJAX、文件上传）用纯 JS 即可覆盖

## 影响与限制

### 已知限制

1. **状态管理**：无客户端路由，页面跳转后状态丢失
   - 缓解：JWT Cookie 持久化登录态；表单数据临时存储在 `localStorage`

2. **用户体验**：页面间完整刷新，不如 SPA 流畅
   - 缓解：AJAX 表单提交避免部分页面刷新；状态流转操作用 fetch + reload

3. **代码复用**：模板间复用靠 `{% extends %}` / `{% include %}`，不如组件化灵活
   - 缓解：base.html 提供统一布局和导航栏

4. **前端 API 调用**：需手动管理 Authorization Header
   - 缓解：`app.js` 封装 `apiFetch()` 自动注入 Token + 401 跳转

## 相关 ADR

- [ADR 01: Python FastAPI + SQLite 技术选型](01-python-fastapi-sqlite.md)
