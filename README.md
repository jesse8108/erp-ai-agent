# ERP AI Agent

ERP 业务管理 AI 对话系统 —— 用 Claude + 飞书替代传统多维表格，让业务员用自然语言管理合同、提货、调度、对账。

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0（异步）
- **数据库**: PostgreSQL 16 + pg_trgm（模糊匹配）
- **AI**: Anthropic Claude Sonnet 4.6（Tool Use 模式）
- **集成**: 飞书自建应用（业务员交互入口）
- **部署**: Docker Compose（开发） / 云服务器 Docker（生产）

---

## 目录结构

```
erp-ai-agent/
├── app/                          # 应用代码
│   ├── main.py                   # FastAPI 入口
│   ├── api/                      # HTTP 路由
│   │   └── health.py             # 健康检查
│   ├── core/                     # 核心模块
│   │   └── config.py             # 配置（pydantic-settings）
│   └── db/                       # 数据库
│       ├── base.py               # SQLAlchemy Base
│       └── session.py            # 异步会话
├── alembic/                      # 数据库迁移
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                 # migration 文件（W1 生成）
├── docker/                       # Docker 相关
│   ├── Dockerfile
│   └── init.sql                  # PG 初始化脚本
├── docs/                         # 设计文档
│   ├── 00-continuation-guide.md
│   ├── 01-project-blueprint.md
│   ├── 02-development-plan.md
│   ├── schema.md                 # 数据库设计（v0.9）
│   └── workflows.md              # 工作流定义（v0.2）
├── data-import/                  # 主数据 Excel
│   ├── brands_master.xlsx
│   ├── products_master.xlsx
│   ├── delivery_locations_master.xlsx
│   ├── brand_aliases_final.xlsx
│   ├── product_aliases_master.xlsx
│   ├── companies_final.xlsx
│   └── aliases_final.xlsx
├── tests/                        # 测试
├── scripts/                      # 工具脚本
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml                # Ruff/Mypy/Pytest 配置
├── alembic.ini
├── .env.example
└── .gitignore
```

---

## 快速开始（Mac 本地开发）

### 前置要求

- Docker Desktop（Apple Silicon 用原生 ARM64 镜像）
- Git
- 一个文本编辑器（VS Code / Cursor 推荐）

### 第 1 步：配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少填入 ANTHROPIC_API_KEY（暂时空着也能启动，只是 AI 功能不可用）
```

### 第 2 步：启动服务

```bash
# 启动（后台运行）
docker compose up -d

# 查看日志
docker compose logs -f app

# 停止
docker compose down

# 完全清除数据（慎用！）
docker compose down -v
```

### 第 3 步：验证启动成功

```bash
# 方式一：浏览器访问
open http://localhost:8000/docs    # 交互式 API 文档
open http://localhost:8000/health  # 应返回 {"status":"ok"}

# 方式二：命令行
curl http://localhost:8000/health
curl http://localhost:8000/health/ready   # 检查 DB + pg_trgm
curl http://localhost:8000/health/info    # 应用详细信息

# 连接 PG（用 DBeaver/TablePlus 连 localhost:5432）
docker compose exec db psql -U erp_dev -d erp_ai
```

预期 `/health/ready` 返回：

```json
{
  "status": "ready",
  "checks": {
    "database": {"status": "ok", "version": "PostgreSQL 16.x ..."},
    "pg_trgm": {"status": "ok"}
  }
}
```

### 第 4 步：代码热重载验证

修改 `app/api/health.py` 里的任何字符串，保存后刷新浏览器，内容应立即更新（无需重启容器）。

---

## 常用开发命令

### Docker

```bash
docker compose up -d              # 启动
docker compose down               # 停止
docker compose restart app        # 重启应用
docker compose logs -f app        # 查看应用日志
docker compose logs -f db         # 查看数据库日志
docker compose exec app bash      # 进入应用容器
docker compose exec db psql -U erp_dev -d erp_ai  # 进入 DB
```

### 数据库迁移（Alembic）

> W1 开始才会真正用到，W0 先确保命令能跑通。

```bash
# 进入应用容器执行
docker compose exec app bash

# 生成新 migration（对比 ORM 和 DB 的差异）
alembic revision --autogenerate -m "create initial tables"

# 查看当前版本
alembic current

# 升级到最新
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 查看历史
alembic history
```

### 代码质量

```bash
# 进入应用容器或本机 venv
docker compose exec app bash

# 格式化代码
ruff format app tests

# 静态检查
ruff check app tests

# 自动修复能修的
ruff check app tests --fix

# 类型检查
mypy app
```

### 测试

```bash
docker compose exec app pytest
docker compose exec app pytest tests/test_health.py -v
docker compose exec app pytest --cov=app --cov-report=term-missing
```

---

## Apple Silicon (M 系列) 注意事项

1. **镜像平台**：`docker-compose.yml` 已显式指定 `platform: linux/arm64`，避免 x86 模拟层导致性能下降 10x+
2. **psycopg v3**：用的是 `psycopg[binary]`，Apple Silicon 上有预编译 wheel，无需 `gcc` 本机编译
3. **命名 volume vs bind mount**：PG 数据用 `erp_ai_pgdata` 命名 volume（不是绑定本地目录），避免 Mac 文件系统大小写不敏感导致的问题
4. **端口冲突**：如果 5432 被本机 PG 占用，改 `docker-compose.yml` 的 ports 为 `"5433:5432"`

---

## 故障排查

### 启动时报 `port 5432 already in use`

```bash
# 看谁占着
lsof -i :5432

# 停掉本机 PG（brew 装的）
brew services stop postgresql

# 或改 docker-compose 端口映射
```

### 启动时报 `exec format error`

Apple Silicon 拉了 x86 镜像。检查 `docker-compose.yml` 是否有 `platform: linux/arm64`，没有就加上，然后：

```bash
docker compose down
docker compose pull
docker compose up -d
```

### `/health/ready` 返回 pg_trgm missing

init.sql 没执行（通常是 volume 已存在旧数据）。清空重来：

```bash
docker compose down -v    # 删 volume
docker compose up -d
```

### 数据库连接报 `FATAL: password authentication failed`

检查 `.env` 的 `DATABASE_URL` 密码是否和 `docker-compose.yml` 里的 `POSTGRES_PASSWORD` 一致。

---

## 下一步

W0 启动成功后，项目进入 **W1: 建库 + 模型层**，按 `docs/02-development-plan.md` 推进：

- 任务 1.1：Python 项目初始化 ✅（本 W0 完成）
- 任务 1.2：数据库 Schema（按 `schema.md v0.9` 建 30 张表 + 5 个视图）
- 任务 1.3：主数据导入（按 schema 附录 B 的顺序）
- 任务 1.4：历史合同/工单/委托/流水数据导入

---

## 设计文档导航

- **项目总览**：`docs/00-continuation-guide.md`
- **架构蓝本**：`docs/01-project-blueprint.md`
- **12 周开发计划**：`docs/02-development-plan.md`
- **数据库设计**：`docs/schema.md`（当前 v0.9）
- **工作流定义**：`docs/workflows.md`（当前 v0.2，下次会话补全到 25-30 个）

---

## License

Proprietary - Internal use only.
