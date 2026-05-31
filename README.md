# HKIA（香港保险配置助手）

HKIA 是面向香港保险配置场景的 AI Agent 产品：以顾问式自然对话收集用户背景，并生成带免责声明的个性化配置说明（详见 `开发文档/`）。

## 阶段路线（摘要）

| 阶段 | 焦点 |
|------|------|
| **0** | 仓库与前后端骨架、环境变量约定、本地启动与自动化验收 |
| **1** | 登录 → 会话 → 多轮对话 → 画像 → 报告 → 知识库 / 市场情报（MVP） |
| **2** | PostgreSQL、Qdrant、LangGraph、检索 trace、会话治理 |
| **3** | 真实产品与行业数据、Docker Compose |
| **4** | 多语言、操作指南、图表与报告体验、运营向权限与 Compose 健康检查 |

当前交付：**阶段 4 产品化增强（本阶段）** — next-intl（zh-CN / en / zh-TW）、公共 `/[locale]/guide` 与登录态 `/[locale]/reference` 操作说明、柔色氛围背景与打印友好样式、报告 12+ 图表类型、JWT `role` + `X-Admin-Key` 双通道管理接口、`ADMIN_BOOTSTRAP_EMAILS`、Compose 各服务 healthcheck；自动化验收见 `scripts/verify_phase4.ps1`。

详情：`开发文档/01-需求边界与阶段路线.md`、`开发文档/04-分阶段验收标准.md`。

## 前置条件

- **Node.js**（建议 LTS），npm
- **Python 3.11+**，pip（或使用 [uv](https://github.com/astral-sh/uv)）

## 环境变量

1. 复制根目录 `.env.example` 为 `.env`
2. 填写 `JWT_SECRET`（建议 32+ 字节随机串）
3. 调用真实模型时填写 `DEEPSEEK_API_KEY`；无密钥时可设 `USE_MOCK_LLM=true` 使用后端内置 mock
4. **不要**将 `.env` 提交到 Git

## 本地启动

需要**两个终端**：先启动后端，再启动前端。

### 后端（FastAPI）

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：<http://127.0.0.1:8000/health>  
首次启动会在数据库中自动建表（默认 SQLite `backend/hkia.db`，或由 `DATABASE_URL` 决定）。若使用 PostgreSQL，建议在 `backend/` 目录执行 `alembic upgrade head` 维护迁移。

### Qdrant / 向量（可选）

1. 启动本地 Qdrant，并在 `.env` 设置 `QDRANT_URL`（示例见 `.env.example`）。
2. 配置 OpenAI 兼容的 `EMBEDDING_API_BASE` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL`；若留空则使用后端确定性 Mock 向量（便于 CI）。
3. 自仓库根目录执行：`python scripts/init_qdrant.py`，将示例产品写入向量库。

### 阶段 3：真实产品导入

1. 准备 CSV/JSON，字段参考：`backend/app/data/phase3_products_seed.example.json`
2. 从仓库根目录执行：

```bash
python scripts/import_products.py backend/app/data/phase3_products_seed.v3.json
```

官网产品目录有更新时，可在仓库根目录重新生成 `v3` 后再导入（需能访问 www.chinalife.com.hk）：

```bash
python scripts/build_chinalife_product_seed.py
python scripts/import_products.py backend/app/data/phase3_products_seed.v3.json
```

导入会写入 `products` / `product_sources`，并在配置了 Qdrant 时自动同步 `review_status=active` 产品向量。

若批量导入时产品中尚为 `pending_review`，可随后将 `review_status` 置为 `active` 并单独同步向量：

```bash
python scripts/activate_phase3_products.py
python scripts/sync_qdrant_active_products.py
```

### 前端（Next.js）

```bash
cd frontend
npm install
npm run dev
```

默认：<http://localhost:3000>（首页会跳转至登录或会话列表）

**首次使用**：打开「注册」创建账号，或使用已有邮箱登录。

说明：若项目路径含非 ASCII 字符（例如中文目录名），Next.js 16 默认 Turbopack 可能在构建/开发时出错；本仓库已将 `dev`/`build` 脚本固定为 **`--webpack`** 以避免该问题。

## 阶段 1 验证（自动化）

从**仓库根目录**（Windows）：

```powershell
.\scripts\verify_phase1.ps1
```

包含：`backend` 的 `pytest`（含 10 轮对话 + 报告 + 知识库/市场接口的 mock LLM 流程）、`frontend` 的 `npm run build`、`frontend` 的 Playwright 冒烟（登录/注册页）。

### 阶段 2 验证（自动化）

```powershell
.\scripts\verify_phase2.ps1
```

### 阶段 3 验证（自动化）

```powershell
.\scripts\verify_phase3.ps1
```

与阶段 1 脚本一致，并在 README 中约定可选 Postgres / Qdrant 手测步骤。

### 阶段 4 验证（自动化）

```powershell
.\scripts\verify_phase4.ps1
```

与阶段 3 相同流水线；Playwright 对简体 UI 使用 **`/zh-CN/login` 等显式路径**，以避免测试浏览器 `Accept-Language` 优先英语时误判。

分别执行可参考：

```bash
cd backend && pytest -q
cd frontend && npm run build
cd frontend && npx playwright install chromium   # 首次 e2e 需要
cd frontend && npm run test:e2e
```

**建议**：在真实 `DEEPSEEK_API_KEY` 下仍手跑一遍「注册 → 会话 → 多轮对话 → 生成报告 → 知识库/市场」，确认延迟与回复质量符合预期（参见 `开发文档/06-合规安全与质量要求.md`）。

## Docker Compose 一键启动

从仓库根目录：

```bash
docker compose up --build
```

### 按地区选择启动方式（Windows）

**推荐**（纯英文文件名，避免 cmd 编码导致闪退）：

| 地区 | 启动脚本 | Docker 环境文件 |
|------|----------|-----------------|
| **中国大陆** | `start-cn.bat` | `docker.cn.env` |
| **境外 / 香港 / 澳门** | `start-intl.bat` | `docker.intl.env` |
| **不确定** | `start.bat` | 输入 1 或 2 |

中文文件名快捷方式（内部转调上述脚本）：`.启动项-境内.bat`、`.启动项-境外.bat`、`.启动项.bat`。

关闭服务仍用 **`.关闭全栈.bat`**（与地区无关）。

### 命令行（可选）

**中国大陆**（直连 Docker Hub 常 `EOF` / `timeout`）：

```powershell
.\scripts\pull_docker_images_cn.ps1
docker compose --env-file docker.cn.env up -d --build
```

**境外 / 香港 / 澳门**：

```powershell
.\scripts\pull_docker_images_intl.ps1
docker compose --env-file docker.intl.env up -d --build
```

若国内镜像源不稳定，可编辑 `docker.cn.env` 中的 `POSTGRES_IMAGE` / `NODE_IMAGE` 等前缀。

默认暴露：
- 前端：<http://localhost:3000>
- 后端：<http://localhost:8000>
- PostgreSQL：`localhost:5432`
- Qdrant：<http://localhost:6333>

Compose 启动后后端会自动执行 `alembic upgrade head`。若需导入产品数据，可在本机继续运行 `python scripts/import_products.py ...`，并用前端完成「注册 → 新会话 → 对话 → 报告」Demo 流程。

各服务已配置 `healthcheck`，`frontend` 依赖 `backend` healthy 后启动。编排环境变量中请设置强随机 `JWT_SECRET`，生产勿使用示例 `hkia` 口令；`ADMIN_API_KEY` 与 `ADMIN_BOOTSTRAP_EMAILS` 见根目录 `.env.example`（阶段四：运营人员管理员名单与脚本用 API Key）。

**备份与轮换（基础）**

- PostgreSQL：对 `postgres_data` 卷定期 `pg_dump`（或云平台自动备份）。
- Qdrant：备份 `qdrant_data` 卷或按运维策略快照。
- 密钥：轮换 `JWT_SECRET`、`ADMIN_API_KEY`、DeepSeek / Embedding 密钥时，先更新运行中环境再滚动重启容器。

**阶段四自动化验证**

```powershell
.\scripts\verify_phase4.ps1
```

## 阶段 0 验证

```powershell
.\scripts\verify_phase0.ps1
```

## 仓库结构

```
frontend/     # Next.js + shadcn + 业务页面 + Playwright e2e
backend/      # FastAPI、SQLAlchemy、LangGraph、pytest
scripts/      # verify_phase0–4、import_products、init_qdrant 等
开发文档/
需求文档/
```

## GitHub 代码托管

> **概念区分**（见 `vibe coding.txt` 第 7、9 节）  
> - **GitHub 托管** = 备份源码、版本回退、协作；**不会**自动让外人打开网站。  
> - **应用上线** = 某台机器 24 小时跑前后端 + 数据库（本机 Tailscale 试点，或云主机 Docker）。  
> - **GitHub Pages** = 仅纯静态 HTML；本项目含 Next.js API 代理、FastAPI、PostgreSQL、Qdrant，**不能**用 Pages 跑完整产品。

### 首次推送到 GitHub（Private 推荐）

本地仓库已初始化（`main` 分支）。在 [GitHub 新建仓库](https://github.com/new) 时：

1. 选 **Private**（含 API 密钥配置说明与业务逻辑）
2. **不要**勾选 “Add a README”（本地已有）
3. 复制 HTTPS 地址，例如 `https://github.com/你的用户名/hkia-assistant.git`

在仓库根目录执行：

```powershell
git remote add origin https://github.com/你的用户名/hkia-assistant.git
git push -u origin main
```

若 GitHub 提示需登录，使用 Personal Access Token 作为密码，或配置 [Git Credential Manager](https://github.com/git-ecosystem/git-credential-manager)。

### 日常更新

```powershell
git add .
git commit -m "说明本次改动"
git push
```

可选基线标签：`git tag v1.0-baseline && git push origin v1.0-baseline`

### 提交前检查

- `.env`、本地 `*.db`、`node_modules/`、`.next/` 已在 `.gitignore` 中，**勿**提交真实密钥
- 仅提交 `.env.example` 作为配置模板

### 若要让同事访问产品（非 GitHub Pages）

| 场景 | 做法 |
|------|------|
| 仅备份代码 | 推送到 GitHub Private（本节） |
| 2～3 人试点、你可常开电脑 | Tailscale + 共享模式启动（`vibe coding.txt` 方案 A） |
| 关机也要用、零安装 | 云轻量主机 + `docker compose up -d --build`（方案 B） |
