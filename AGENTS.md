# 项目开发规范（AGENTS.md）

> 本文件给所有协助开发本项目的 AI 工具（OpenAI Codex / Claude / Cursor 等）阅读。
> 任何代码生成必须严格遵守以下规范。

---

## 1. 项目概述

ERP AI 对话系统：用 AI 对话方式替代飞书多维表格的 ERP 操作。业务员通过飞书与 AI 对话完成合同、提货、流水的 CRUD。

**完整背景见 `docs/00-continuation-guide.md` 和 `docs/01-project-blueprint.md`，必须先读完再开始工作。**

---

## 2. 技术栈（已锁定，不可更改）

- **语言**: Python 3.11+
- **Web 框架**: FastAPI
- **ORM**: SQLAlchemy 2.0（async 模式）
- **数据库迁移**: Alembic
- **数据库**: PostgreSQL 16 + pg_trgm 扩展
- **LLM**: 通过 Hermes 调用 OpenAI（仅用作调用代理）
- **任务调度**: APScheduler
- **测试**: pytest + pytest-asyncio
- **Lint**: ruff + black
- **类型检查**: mypy（核心模块 strict mode）
- **容器**: Docker + docker-compose
- **飞书**: 官方开放平台 SDK (`lark-oapi`)

不要引入额外的框架或库（除非项目蓝本明确允许）。

---

## 3. 核心原则（每条都不可违反）

### 3.1 数据完整性

1. **所有数据库修改必须在事务内**
   ```python
   async with session.begin():
       # 所有 insert/update/delete
   ```
   
2. **所有写操作必须产生 audit_log 记录**（在同一事务内）
   
3. **业务表的每次 INSERT/UPDATE/UPDATE-as-soft-delete 必须同事务写对应 history 表**
   - 不要用 DB 触发器，用应用代码显式写
   - 原因：需要关联 audit_log_id（触发器拿不到）

4. **严禁物理删除业务数据**
   - 所有业务表用软删除（`deleted_at` 字段）
   - DB 层 `REVOKE DELETE` 权限阻止误操作
   - 只有 transactions 表的特定 TRIGGER 阻止原始字段更新

### 3.2 价格与数量约束

5. **合同的 quantity_tons 和 unit_price 是真源**
   - 工单/委托的 `unit_price` 必须等于对应合同的 `unit_price`
   - 创建工单/委托时自动从合同拷贝，不允许手改
   - 改价必须走"修改合同"workflow

6. **聚合字段不存储**
   - 已提货量、敞口库存、应收应付、总佣金、保证金金额都通过 VIEW 实时计算
   - 不要在业务表里加这些"冗余"字段

### 3.3 AI 安全

7. **MCP 工具必须强制注入 current_user_id**
   - 不信任 LLM 传的 user_id 参数
   - 后端在调用前用当前会话的 user_id 覆盖
   
8. **AI 不做计算、不做判断**
   - 所有数字必须来自工具返回
   - 所有规则校验在 Python 代码里
   - 所有写操作必须先生成 Plan → 用户确认 → 执行

9. **查询工具默认过滤软删除记录** (`WHERE deleted_at IS NULL`)
   - 在 SQLAlchemy ORM 基类层实现
   - 管理员特殊视图除外

---

## 4. 开发纪律

1. **每个新模块必须有 README.md**
   - 说明：功能、输入、输出、使用示例、测试命令

2. **每个 public 函数必须有 docstring**（Google 风格）
   ```python
   def foo(x: int) -> str:
       """Convert int to str.
       
       Args:
           x: The integer to convert.
       
       Returns:
           String representation.
       
       Raises:
           ValueError: If x is negative.
       """
   ```

3. **测试覆盖率**：核心业务逻辑 > 80%
   - workflow / rule / executor 必须有测试
   - 边界情况必须覆盖（数量为 0、负数、超限、并发等）

4. **提交前必须跑 pytest 且全部通过**

5. **代码必须过 `ruff check .` 和 `mypy app/` 无 error**

6. **每周完成一组任务后打 git tag**（如 `v0.3-week3`）

---

## 5. 禁止事项

- ❌ 禁止硬编码业务常量（合同号、用户 ID、金额阈值、魔法数字）
  - 用配置文件、环境变量、或数据库配置表
  
- ❌ 禁止在 AI prompt 里用 f-string 直接拼用户输入
  - 防 prompt injection
  - 用结构化的 message 模板
  
- ❌ 禁止在业务逻辑里用 `os.system` / `eval` / `exec`

- ❌ 禁止跳过测试提交

- ❌ 禁止用 DB 触发器实现 history 表写入
  - 例外：transactions 表的"原始字段保护 TRIGGER"是允许的

- ❌ 禁止给业务员暴露危险工具
  - 比如"直接执行 SQL"工具
  - 比如"绕过审批执行 plan"工具

- ❌ 禁止 AI 工具白名单外的工具调用
  - 用户身份对应可用工具列表，越权直接拒绝

- ❌ 禁止用 CASCADE 外键
  - 软删除场景下 CASCADE 会造成连带误删
  - 关联表的孤儿记录由审计规则检测处理

---

## 6. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `ContractWorkflow` |
| 函数/变量 | snake_case | `create_sales_contract` |
| 常量 | UPPER_SNAKE_CASE | `MAX_QUANTITY_TONS` |
| 数据库表 | snake_case 复数 | `delivery_orders` |
| 数据库字段 | snake_case | `quantity_tons` |
| Enum 值 | snake_case | `'fixed_ratio'` |
| 文件名 | snake_case | `update_contract.py` |
| Workflow 名 | snake_case | `create_sales_contract` |
| Git commit | "Week N: 简短说明" | `Week 3: 实现首个 workflow` |

---

## 7. 项目结构

```
erp-ai-agent/
├── docs/                       # 项目文档
│   ├── 00-continuation-guide.md
│   ├── 01-project-blueprint.md
│   ├── 02-development-plan.md
│   ├── schema.md
│   ├── workflows.md
│   └── aliases.xlsx
├── app/                        # 源代码
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置（pydantic-settings）
│   ├── db/
│   │   ├── session.py          # SQLAlchemy session
│   │   └── models/             # ORM 模型
│   ├── api/                    # FastAPI 路由
│   ├── services/               # 通用业务服务
│   ├── workflows/              # workflow 定义
│   ├── rules/                  # 业务规则
│   ├── audit/                  # 审计引擎
│   ├── tools/                  # MCP 工具
│   ├── agent/                  # Agent 编排
│   ├── gateway/                # 飞书 Gateway
│   └── utils/
├── tests/                      # 测试
├── alembic/                    # 数据库迁移
├── scripts/                    # 运维脚本
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── AGENTS.md                   # 本文件
├── README.md
└── .env.example
```

---

## 8. 开发工作流

### 8.1 标准任务流程

```
1. 阅读 docs/02-development-plan.md 中本周任务部分，理解目标
2. 阅读 docs/schema.md 和 docs/workflows.md 中相关部分
3. 实现代码
4. 写测试
5. 跑 pytest，全过
6. 跑 ruff check + mypy，无 error
7. git add / commit / push
8. 用户验收 → 通过则打 tag
```

### 8.2 涉及数据库的开发

1. 改 schema 必须用 Alembic migration（不要手动改表）
2. migration 文件必须 review，确认：
   - 升级和回滚都正确
   - 索引建好
   - 不破坏已有数据
3. 上线前必须在测试库跑一遍 migration

### 8.3 涉及 workflow 的开发

每个 workflow 必须包含：
- `validate_params(params)` - 参数校验
- `check_permission(user_id, params, db)` - 权限检查
- `plan(params, user_id, db) -> Plan` - 生成方案（含规则校验）
- `verify_post_execution(plan, db)` - 事后核验

并且必须有：
- 至少 5 个测试用例（正常 + 边界 + 异常）
- 详细的 docstring（参考 `docs/workflows.md` 对应 workflow 的定义）

### 8.4 涉及查询工具的开发

每个查询工具必须：
- 第一参数必须是 `_current_user_id`（强制注入）
- 内部调用 PermissionChecker 过滤数据
- 默认 `WHERE deleted_at IS NULL`
- 返回结构化数据（pydantic model），不是 dict

---

## 9. 关键决策提醒（不要尝试改动）

这些决策已在文档中确定，不要质疑或建议改变：

1. ❌ 不要建议用 Hermes 的 memory/skill 系统
2. ❌ 不要建议让 AI 自主规划多步操作（必须用预定义 workflow）
3. ❌ 不要建议让 AI 直接生成 SQL 或调用底层工具
4. ❌ 不要建议在 transactions 表加 contract_id 等对账字段
5. ❌ 不要建议把工单/委托的 unit_price 设为可独立修改
6. ❌ 不要建议物理删除（用软删除）
7. ❌ 不要建议撮合合同 (`brokering`) 计算应收应付
8. ❌ 不要建议把 user_id 暴露给 LLM（必须后端注入）
9. ❌ 不要建议用 DB 触发器实现 history 表（transactions 的字段保护 TRIGGER 除外）

---

## 10. 提问与澄清

如果遇到以下情况，**必须先问用户，不要自己决定**：

- 文档中没有明确说明的字段或规则
- 业务场景不清楚的边界情况
- 需要在两种实现方案中选择
- 涉及性能与安全的权衡
- 需要新增表或修改 schema 时

不要假设、不要猜测。**澄清的成本远低于返工的成本**。

---

## 11. 安全要求

1. **敏感信息不进 Git**
   - 飞书 App Secret、数据库密码、OpenAI key 等放 `.env`
   - `.gitignore` 必须包含 `.env`、`*.key`、`*.pem`
   
2. **身份证等 PII 加密存储**
   - `dispatches.driver_id_number` 用 AES-GCM 加密
   - 应用层 SQLAlchemy TypeDecorator 自动加解密
   - AI 查询时默认打码显示

3. **API 限流**
   - 每用户每分钟最多 20 条消息
   - 全局 LLM 调用速率限制
   - 防止恶意刷流量

4. **审计完整性**
   - 任何写操作必有 audit_log
   - 任何 audit_log 必关联 plan_id
   - 任何 plan_id 必关联 conversation_id（如来自 AI）

---

## 12. 测试要求

### 12.1 必须测试的场景

- 正常路径（happy path）
- 参数边界（0、负数、超大值）
- 权限拒绝
- 软删除后的查询过滤
- 并发情况（乐观锁）
- 事务回滚
- 历史表写入正确性

### 12.2 不要测试的场景

- 第三方库的内部行为（如 SQLAlchemy 的 ORM 转换）
- LLM 的具体输出（mock 掉）
- 飞书 API 的真实调用（用 fixture）

---

## 13. 与其他 AI 协作

如果用户让你 review 其他 AI 生成的代码：

1. 先读 `docs/02-development-plan.md` 对应周次的目标
2. 检查是否符合本文件所有规范
3. 检查测试覆盖
4. 检查安全隐患（SQL 注入、权限绕过、事务边界）
5. 给出**具体修改建议**（不只是"建议改进"）
6. 如果有重大设计问题，直接说出来，不要客气

---

## 14. 联系

- 项目发起人：[填你的名字]
- 决策权：所有架构决策由发起人确认
- 紧急情况：[填联系方式]

---

*v1.0 - 2026-04-20*
*本文件随项目演进持续更新*