# 会话延续文档

> **目的**: 本文档让你（项目发起人）在开启新对话时，把这份文档贴给新的 Claude，能立刻理解项目的全貌、当前进度、设计决策、接下来的任务。
>
> **使用方式**:
> 1. 新开 Claude 对话
> 2. 把以下 5 份文档都上传或贴给 Claude：
>    - 本文件（00-continuation-guide.md）
>    - 01-project-blueprint.md（项目蓝本）
>    - 02-development-plan.md（12 周开发计划）
>    - schema.md v0.9（数据库设计）
>    - workflows.md v0.2（工作流定义）
> 3. 告诉新 Claude："先读完这些文档再回答我的问题"
> 4. 开始提你的新问题

---

> ⚠️ **给新 Claude 的最关键提醒**：本项目开发主力是 **OpenAI Codex**，不是 Claude。
> Claude 的职责是**需求分析 + 架构设计 + 写 Codex 任务书**，**不是直接写业务代码**。
> 详细分工见【第六节 Claude vs Codex 工作流分工】。
> 如果用户让你"写代码"，先停下来确认：这是要你写代码，还是要你写给 Codex 的任务书。

---

## 一、项目一句话

用 AI 对话方式替代飞书多维表格的 ERP 操作；PG 作为唯一真源；Hermes 只做 LLM 调用后端。业务员通过飞书与 AI 对话完成合同、提货、流水的 CRUD，AI 生成 Plan 预览 → 用户确认 → 审批 → 执行，全程可审计。

---

## 二、业务背景

### 公司主体结构（非常重要）

| 公司名 | 代号 | 角色 |
|-------|------|------|
| 安徽趋易贸易有限公司 | `subject_a` | **我方主体**，直接参与销售/采购合同 |
| 上海瞿谊实业有限公司 | `subject_b` | **我方主体**，直接参与销售/采购合同 |
| 上海骋子次方商务服务有限公司 | (不入数据) | 撮合主体，只做中介，不作为合同甲乙方 |

**关键约束**：
- 主体 A 和主体 B 之间**不会有内部交易**
- 撮合主体 C 不作为合同数据中的一方
- 撮合业务在系统中通过 `contract_type='brokering'` 标识，两边都是外部公司

### 7 种合同类型

| 大类 | 小类 (enum) | 我方角色 | 我方主体参与 |
|------|------------|---------|-------------|
| 销售 | `sales` | seller | ✅ 甲方 |
| 采购 | `purchase` | buyer | ✅ 乙方 |
| 撮合 | `brokering` | broker_only | ❌（纯中介）|
| 撮合 | `brokering_sales` | seller | ✅ 甲方 |
| 撮合 | `brokering_purchase` | buyer | ✅ 乙方 |
| 借货 | `lending_sales` | lender | ✅ 甲方 |
| 借货 | `lending_purchase` | borrower | ✅ 乙方 |

### 核心业务流程

```
销售合同 →(1:N) 提货工单 →(1:N) 车辆调度 →(N:1) 提货委托 →(N:1) 采购合同
```

**所有提货都由销售合同发起**。工单是入口，委托是产物。一个工单可能拆多车，一车可能挂一个或多个委托（因为货源可能来自不同采购合同）。

### 6 名业务员

| 姓名 | 历史合同数 | 推测角色 |
|------|----------|---------|
| 李成子 | 82 | sales + broker |
| 祝晓彤 | 43 | sales |
| 黄佳欣 | 33 | broker（撮合较多）|
| 游鑫淼 | 17 | sales |
| 陈凯丽 | 9 | sales |
| 邢光 | 创建全部 250 条 | admin + clerk（代录入）|

### 历史数据量

- 250 条合同（2026-03）
- 64 条工单 + 58 条委托 + 37 条调度
- 713 条流水（2026-02-28 到 2026-03-31）

### 主要品牌

三房巷（93）、万凯（46）、大连逸盛（21）、海南逸盛（20）、华润（18）、华润圆粒子（12）、百宏（10）、昊源（9）、仪征（9）、富海（8）等

### 主要提货地

江阴（115）、海宁（46）、基价仓库（41）、常州（18）、阜阳（9）、仪征（9）、东营（8）、吴江（2）、上海（2）

---

## 三、核心设计决策（14 条，不可动摇）

1. **AI 是翻译官，不是决策者**：只理解意图、填参数、自然语言化；不做业务判断、不做多步规划、不自主写库
2. **所有写操作必经 Plan**：propose → confirm → approve → execute 四阶段
3. **业务约束代码化**：LLM 不做规则判断，规则是 Python 代码
4. **查询必有证据**：所有数字来自工具返回，后置校验防幻觉
5. **审计闭环自愈**：异常自动发现、自动归档、自动分配给负责人、问题消失自动关闭
6. **完整追溯链**：对话 → Plan → 审批 → 执行 → 历史数据，任意一端可回溯
7. **用户身份强制注入**：工具调用的 user_id 由后端注入，不信任 LLM
8. **聚合字段不存储，通过 VIEW 计算**：已提货量、敞口库存、应收应付、总佣金、保证金金额
9. **合同数量和单价是真源**：工单/委托的 unit_price 必须等于合同，不可绕过
10. **严禁物理删除**：全局软删除机制 (`deleted_at`)；区分"作废"(status=cancelled) vs "删除"(deleted_at 有值)
11. **流水表只读**：原始字段永不可改（TRIGGER 保护），对账通过视图实现汇总对账
12. **调度拆分规则**：提货地/品牌/型号任一不同必须拆成独立调度记录，编号规则 `DD-YYYYMMDD-NNN[-A/B/C]`
13. **价格偏离是警告不是错误**：调度的品牌/型号/提货地可以与合同不一致（业务允许），但审计规则会提醒
14. **审计表和 history 表只允许 INSERT + SELECT**：PG 权限层阻止

---

## 四、技术架构

### 技术栈（已锁定）

- **语言**: Python 3.11+
- **Web**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **迁移**: Alembic
- **数据库**: PostgreSQL 16 + pg_trgm 扩展
- **LLM**: Hermes（OpenAI 会员）→ 仅用作 LLM 调用代理，不用其 memory/skill/gateway
- **任务调度**: APScheduler
- **容器**: Docker + docker-compose
- **飞书**: 官方开放平台 SDK

### 系统分层

```
飞书 → Gateway → Agent（会话管理） → Hermes → OpenAI
                    ↓
                 MCP Tools（查询工具 / workflow 触发）
                    ↓
                 Workflow 引擎 → 规则引擎 → PostgreSQL
                    ↓
                 审批引擎 / 审计引擎 / History 写入
```

### 独立定时任务

- 审计引擎（APScheduler）→ 检测异常 → pending_issues → 飞书多维表格同步
- 日报生成 → 推送飞书给老板
- 流水导入（每日/每周人工触发）
- PG 备份 → 对象存储

---

## 五、数据库设计概况

### 30 张表 + 5 个视图（第 1 周 Codex 一次建完）

**业务表 + history 表（10 张）**:
- contracts + contracts_history
- delivery_orders + delivery_orders_history
- delivery_delegations + delivery_delegations_history
- dispatches + dispatches_history
- transactions + transactions_history

**主数据表（5 张）**:
- users / companies / brands / products / delivery_locations

**别名表（3 张）**:
- company_aliases / brand_aliases / product_aliases

**审计三件套（3 张）**:
- audit_logs / change_proposals / approval_records

**AI 运行表（4 张）**:
- conversations / messages / pending_issues / tool_call_logs

**配置表（5 张）**:
- user_permissions / approval_rules / audit_rule_configs / role_holders / leave_records

**视图（5 个）**:
- v_contracts_with_aggregates - 合同聚合视图（含应收应付）
- v_transactions_normalized - 规范化流水（通过 aliases 映射公司名）
- v_transaction_balance_by_counterparty - 按对方公司汇总流水
- v_contract_balance_by_counterparty - 按对方公司汇总合同应收应付
- v_reconciliation - **最终对账视图**（FULL OUTER JOIN）

**TRIGGER / 权限**:
- TRIGGER：transactions 原始字段不可修改
- REVOKE DELETE ON transactions, audit_logs, 所有 history 表
- REVOKE UPDATE ON audit_logs, 所有 history 表

### 关键公式：应收应付计算

**四种分支（见 schema.md 1.4 节完整 CASE WHEN）**：

1. **借货合同**: `保证金金额 + 额外费用`
2. **全款**: `合同总金额 + 额外费用`
3. **按比例扣除** (proportional): `已提货量 × 单价 × (1 - 保证金率) + 保证金金额 + 额外费用`
4. **最后扣除** (at_end):
   - 剩余可提量 > 保证金对应吨数 → `已提货量 × 单价 + 保证金金额 + 额外费用`
   - 剩余 ≤ 保证金对应吨数 → `合同总金额 + 额外费用`（锁定最终金额）

**撮合合同（纯 brokering）**不计算应收应付，只计算佣金。

---

## 六、Claude vs Codex 工作流分工（重要！）

> **这条规则必须在每次会话开始时就明确，避免 Claude 越界抢 Codex 的活**

### 6.1 为什么要分工

本项目的开发主力是 **OpenAI Codex**（通过 GPT 会员订阅）。Claude 作为会话助手，角色是**需求分析 + 架构设计 + 任务书生成 + Review 答疑**，**不是写生产代码的那一位**。

原因：
- Codex 有独立的代码库上下文（能跨文件理解、迭代维护代码）
- Claude 上下文窗口有限，不适合长期维护一个快速迭代的代码库
- 用户已按月付费 Codex，需要让它充分干活

### 6.2 任务分工矩阵

| 任务类型 | Claude（本对话） | Codex | 用户 |
|---|---|---|---|
| 业务建模、概念设计 | ✅ 主 | ❌ | ✅ 决策 |
| schema.md 设计与迭代 | ✅ 主 | ❌ | ✅ 决策 |
| workflows.md 工作流定义 | ✅ 主 | ❌ | ✅ 决策 |
| 主数据清洗（xlsx 处理） | ✅ 主 | ❌ | ✅ review |
| 审批策略 / 权限设计 | ✅ 主 | ❌ | ✅ 决策 |
| **写 Codex 任务书（docs/tasks/WX-*.md）** | ✅ **主** | ❌ | - |
| 业务代码（API/ORM/service） | ❌ | ✅ 主 | ✅ review |
| 数据库 migration（alembic） | ❌ | ✅ 主 | - |
| 测试用例 | ❌ | ✅ 主 | - |
| 历史数据导入脚本（import_*.py） | ❌ | ✅ 主 | ✅ review |
| 代码 review、bug 排查 | ✅ 协助 | - | ✅ 主 |
| 调试启动错误 / 环境问题 | ✅ 协助 | ✅ 协助 | - |

### 6.3 Claude 每次会话开始时必须做的

任何新会话，**读完 continuation-guide 之后**，Claude 都要确认：

1. 当前在做的是 Claude 的工作还是 Codex 的工作
2. 如果是 Codex 的工作（写业务代码），Claude 要做的是**生成任务书**，**而不是**直接写代码
3. 例外：已经存在的 W0 骨架代码（见 6.5 节）是特殊情况，今后的代码全走 Codex

### 6.4 Codex 任务书的标准格式

每个开发任务对应一份 `docs/tasks/WX-任务名.md`，包含以下章节：

```
# W1 任务 1.2：数据库 Schema 建表

## 任务目标
用 SQLAlchemy 2.0 ORM 定义所有表 + 用 Alembic 生成首个 migration

## 前置条件
- W0 已完成（docker compose up 成功，/health/ready 通过）
- 依赖文档：schema.md v0.9

## 技术决策（已锁定，不要改）
- SQLAlchemy 2.0（异步）
- UUID 用 `uuid.UUID` + `sa.UUID(as_uuid=True)`
- 时间字段一律用 `DateTime(timezone=True)`
- ...

## 文件清单
- app/db/models/contracts.py（含 contracts 表的 ORM）
- app/db/models/users.py
- ...（列全）

## 实现要点
- 软删除字段统一用 schema.md 0.5.3 节的规范
- UNIQUE 约束注意：软删除表用 `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL`
- ...

## 验收标准
1. `docker compose exec app alembic upgrade head` 成功
2. 能用 `psql` 看到 30 张表 + 5 个视图
3. `docker compose exec app pytest` 全绿
4. `ruff check app` 无错误
5. `mypy app` 无错误

## 不在本次任务范围内
- 业务代码（留到 W2）
- API 路由（留到 W2）
```

用户把这份任务书贴给 Codex，Codex 按清单交付代码。

### 6.5 W0 特殊情况说明

**W0 Docker 骨架代码是 Claude 直接写的**（2026-04-21），违反了上述分工规则，原因：

- W0 范围小且固化（一次性搭建）
- 技术决策已全部确认（PG 16 + psycopg v3 + SQLAlchemy 2.0 + ARM64）
- 用户希望今天就能看到 `docker compose up` 效果

**从 W1 开始严格走 Codex 流程**——Claude 先出任务书，用户再贴给 Codex 执行。

### 6.6 下次会话开始时的检查清单

新 Claude 接手时，心里过一遍：

- [ ] 读完了 continuation-guide？
- [ ] 确认当前任务归属 Claude 还是 Codex？
- [ ] 如果是 Codex 的任务，生成的是**任务书 `.md`** 还是**代码 `.py`**？
- [ ] 遇到用户请求"帮我写 XXX 代码"时，确认是不是应该改成"帮你写 Codex 任务书"？

---

## 七、当前项目阶段

### 已完成文档（✅）

1. ✅ **01-project-blueprint.md**：项目蓝本（架构、设计哲学、子系统设计）
2. ✅ **02-development-plan.md**：12 周开发计划（每周 codex 任务模板）
3. ✅ **schema.md v0.9**：数据库 schema（~2990 行，brand_aliases / product_aliases 完整设计 + AI 简称查询逻辑）
4. ✅ **workflows.md v0.2**：12 个核心 workflow 定义（新增 create_company + delete_alias）
5. ✅ **00-continuation-guide.md**：本文档
6. ✅ **客户档案清洗成果**（2026-04-21）:
   - `companies_final.xlsx`：1679 家客户的清洗版本（W1 直接导入）
   - `aliases_final.xlsx`：3432 条简称（W1 直接导入）
   - 历史 22 组重复已合并、11 条垃圾数据已删除、1 条已倒闭已标注
7. ✅ **品牌/型号/提货地主数据**（2026-04-21，从客户 PostgreSQL 导出）:
   - `brands_master.xlsx`：34 个品牌
   - `products_master.xlsx`：45 个型号（按品牌分组）
   - `delivery_locations_master.xlsx`：55 个提货地（**品牌专属**，含经纬度/行政区编码/排序权重）
8. ✅ **简称表**（2026-04-21，已 review）:
   - `brand_aliases_final.xlsx`：46 条品牌简称（业务员 review 通过，0 冲突）
   - `product_aliases_master.xlsx`：77 条型号简称（28 非歧义 + 49 歧义；歧义统一标 `is_ambiguous=true`，AI 反问品牌）
   - `brand_aliases_review_summary.md` / `product_aliases_review_summary.md`：决策记录

### 待完成文档（⏳）

1. ⏳ **audit-rules.md**：审计规则清单（第 10 周前完成）
2. ⏳ **queries.md**：日常查询场景清单（第 8 周前完成）
3. ⏳ **business-defaults.md**：业务默认值规则（第 7 周前完成）
4. ⏳ **business 二次 review product_aliases**：确认 WK801/YSW01 这种去横杠简写是否真用（不用就删 8 行），确认是否补充其他口头叫法

### 开发阶段（当前：第 -1 周，准备期）

**第 0 周（准备工作，进行中）**:
- [x] 购买云服务器
- [x] 申请飞书自建应用
- [x] 创建 GitHub 私有仓库
- [x] 配置 OpenAI Codex + GPT 会员
- [x] 确定 6 个业务员的飞书 open_id
- [x] 客户档案清洗完成
- [x] 品牌/型号/提货地主数据梳理完成
- [x] 品牌简称 review 完成（46 条，0 冲突）
- [x] 型号简称生成完成（77 条，含歧义标记）
- [x] Mac 本地 Docker 开发环境搭建（W0 骨架完成，26 个文件，见下述 W0 交付清单）
- [x] 员工表 + 角色权限表梳理完成（10 人 + 7 角色）
- [ ] 业务员二次 review product_aliases（确认去横杠简写是否真用）
- [ ] 工商信息 API 接入方案确定（供 `create_company` workflow 使用）
- [ ] **补全 workflows.md 到 25-30 个**（下次会话的核心任务）
- [ ] **新建 approval-policy.md**（基于已定架构：保留原架构，老板平级，严格防自审）

---

### 🔖 下次会话专注做的事（TODO 清单）

> **优先级：P0，阻塞 W1**（approval_rules 表需要初始种子数据）

1. **补全 workflows.md 从 12 个 → 25-30 个**
   - 当前缺口（Round 2 操作矩阵分析得出）：
     - ❌ `create_delivery_order` 业务员 vs 单证发起的差异
     - ❌ `delete_delivery_order`（业务员申请链 vs 单证发起链）
     - ❌ `create_delivery_delegation` / `delete_delivery_delegation`（仅单证可发起）
     - ❌ `update_dispatch`（业务员申请 → 一级单证）
     - ❌ `create_dispatch` 是否审批
     - ❌ 流水录入流程（出纳不参与，是谁录？AI 从银行流水导？）
     - ❌ `update_contract` 子分类（改单价/数量/对方影响不同）
     - ❌ 业务员修改工单需求（schema 禁止 update → 删旧建新？）
     - ❌ 公司简称 CRUD、品牌简称 CRUD、型号简称 CRUD
     - ❌ 修改公司工商信息（电话/地址变更）
     - ❌ 主数据维护（增/删品牌、型号、提货地）

2. **新建 docs/approval-policy.md**（基于已定架构，不重新设计）
   - 角色映射表（JS-001~JS-009 ↔ 具体人 ↔ 飞书 open_id）
   - 统一审批阈值表（把 workflows 里所有审批规则汇总）
   - 防自审规则（陈凯丽 JS-002+JS-004 场景：自己发的另一人审）
   - 老板平级规则（李成子/邢光 任一人审即可）
   - 请假转移逻辑（role_holders + leave_records）
   - 飞书审批卡片格式设计
   - 审批超时规则（超过 24h 自动升级/提醒？）

3. **生成 approval_rules 种子 SQL**（W1 建库后直接灌）

---

### 🔖 W0 交付清单（2026-04-21 完成）

本地开发环境 Docker 骨架，26 个文件，首次 `docker compose up -d` 应能跑起来并通过 `/health/ready` 检查。

```
erp-ai-agent/
├── docker-compose.yml              # PG 16 + FastAPI 编排（ARM64 原生）
├── docker/
│   ├── Dockerfile                  # Python 3.12 多阶段构建
│   └── init.sql                    # 启用 pg_trgm / uuid-ossp / pgcrypto
├── requirements.txt                # FastAPI 0.115 / SQLAlchemy 2.0 / psycopg v3 / alembic / anthropic / lark-oapi
├── pyproject.toml                  # Ruff + Mypy + Pytest 配置
├── alembic.ini                     # 时区 Asia/Shanghai
├── alembic/
│   ├── env.py                      # 异步迁移（单一真源从 settings 读 URL）
│   ├── script.py.mako              # 新 migration 模板
│   └── versions/
│       └── 20260421_0001_initial_placeholder.py  # W0 占位，验证 alembic 能跑
├── app/
│   ├── main.py                     # FastAPI + lifespan 钩子
│   ├── core/config.py              # pydantic-settings
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy 2.0 DeclarativeBase
│   │   ├── session.py              # 异步 Session + get_session
│   │   └── models/                 # W1 放 ORM models
│   └── api/
│       └── health.py               # /health /health/ready /health/info
├── tests/test_health.py            # 第一个基础测试
├── .env.example                    # 环境变量模板
├── .gitignore                      # 保护 .env
└── README.md                       # 完整启动说明 + 故障排查

启动: docker compose up -d
验证: curl http://localhost:8000/health/ready
```

**关键技术决策锁定**：
- PG 16（pg_trgm 必须）
- psycopg v3（`postgresql+psycopg://` URL 前缀）
- SQLAlchemy 2.0 异步
- Apple Silicon 原生 ARM64（避免模拟层）
- Ruff 替代 black+isort+flake8

---

**第 1 周（项目骨架 + 数据库，未开始）**:
- 任务 1.1: Python 项目初始化（FastAPI + Docker）✅ W0 已完成
- 任务 1.2: 数据库 Schema（按 schema.md v0.9 建 30 张表 + 5 个视图）
- 任务 1.3: 主数据导入（按附录 B 的顺序：brands → products → delivery_locations → brand_aliases → product_aliases → companies + company_aliases）
- 任务 1.4: 历史合同/工单/委托/流水数据导入（按 5b 章映射旧品牌名）

**第 2 周到第 12 周**：按开发计划文档推进

---

## 八、关键对话历史与重要决策记录

### 关于应收应付公式的核心结论

用例：100 吨 × 8000 元 × 保证金 10% = 合同总 80 万、保证金 8 万

- **全款**：应收恒为 80 万 + 额外费用
- **按比例扣除 + 已提 33 吨**：`33 × 8000 × 0.9 + 80000 = 317,600` + 额外费用
- **最后扣除 + 已提 33 吨**：`33 × 8000 + 80000 = 344,000`（剩余 67 吨 > 10 吨，按全额）
- **最后扣除 + 已提 92 吨**：`= 800,000`（剩余 8 吨 ≤ 10 吨，锁定合同总金额）
- **借货**：应收 = 80,000 + 额外费用

### 关于调度拆分规则的结论

**同一工单，提货地/品牌/型号三个维度任一不同 → 必须拆成独立调度**。

编号规则：
- `DD-YYYYMMDD-NNN`（不拆分）
- `DD-YYYYMMDD-NNN-A/-B/-C`（拆分后加后缀）

这三个字段是"**实际物流记录**"，可以和合同约定不同（业务允许），不影响价格。价格始终按合同单价结算，偏离通过审计规则提醒。

### 关于流水表的结论

- 流水表 = 银行流水的忠实副本，**原始字段不可修改**（TRIGGER 保护）
- **不在流水表关联合同**（没有 contract_id / purpose 字段）
- 对账模式：按 **(我方主体 × 对方公司)** 汇总，通过视图 `v_reconciliation` 实现
- 公司名规范化靠 `company_aliases` 表映射
- FULL OUTER JOIN 覆盖三种场景：合同有流水无 / 流水有合同无 / 两者都有
- 流水表只通过 `import_transactions` workflow 写入

### 关于软删除的结论

**区分两个层面**：

| 场景 | 本质 | 使用字段 | 查询时 |
|------|------|---------|--------|
| 合同业务上终止 | 业务行为 | `contract_status = 'cancelled'` | 正常显示，标注已作废 |
| 合同录错了/重复 | 数据行为 | `deleted_at` 有时间戳 | 默认过滤，不显示 |

主数据表（users, companies, brands, products, delivery_locations）不用 deleted_at，用 `is_active`。

UNIQUE 约束改为**部分唯一索引**：`WHERE deleted_at IS NULL`，允许删除后复用。

### 关于价格模型的结论

**合同的数量和单价是整个价格体系的真源，不可被下游工单/委托绕过**：

- 工单/委托的 unit_price 必须等于对应合同的 unit_price
- 业务员创建工单/委托时自动拷贝，不允许手改
- 改价必须走"修改合同"workflow
- 品牌/型号/提货地的变化（在调度层）不影响价格
- 额外费用通过 `extra_fee` / `extra_payment` 字段记录，独立于单价

---

## 九、下一步任务优先级

### 立即要做（本周）

1. **发起人 review 本文档 + 4 份配套文档**（2-3 小时）
2. **发起人开始第 0 周准备工作**（云服务器、飞书应用、GitHub 仓库）
3. **发起人整理 aliases.xlsx**（1-2 小时，找业务员开会）

### 短期（第 1-2 周）

4. 确定 6 个业务员的飞书 open_id
5. 让 Codex 建 30 张表 + 5 个视图（按 schema.md 第 1 周任务模板）
6. 让 Codex 做历史数据导入

### 中期（第 3-5 周）

7. Workflow 引擎框架开发
8. 实现 create_sales_contract 和 update_contract_quantity（打通 Plan 生成和执行）
9. 接入 LLM + 会话管理 + CLI 对话测试

### 长期（第 6-12 周）

10. 飞书 Gateway
11. 审批流
12. 剩余 8 个 workflow
13. 审计引擎 + 待办系统
14. 灰度测试 + 上线

---

## 十、新对话中可能的问题类型

### 类型 A：继续完善设计文档

- "帮我写 audit-rules.md"
- "business-defaults.md 该怎么写"
- "queries.md 的模板和样例"

**新 Claude 的处理方式**：参考 01-project-blueprint.md 第 9 节的描述 + schema.md + workflows.md 相关内容。

### 类型 B：给 Codex 的具体任务

- "第 1 周的 Codex 任务应该怎么出"
- "Codex 做出来的 schema 代码怎么 review"

**新 Claude 的处理方式**：参考 02-development-plan.md 的每周任务模板；用 schema.md 的 DDL 作为标准答案对照。

### 类型 C：业务场景调整

- "我发现 XX 业务场景，schema 需要改"
- "XX workflow 有新需求"

**新 Claude 的处理方式**：
1. 先理解业务场景
2. 评估对 schema / workflows / 其他文档的影响
3. 提出修改方案，标明影响范围
4. 生成更新后的文档

### 类型 D：开发期间的问题

- "Codex 生成的代码有问题"
- "我这里报了个错"

**新 Claude 的处理方式**：参考开发计划里的"Claude 审查模板"，做代码审查。

### 类型 E：项目运营问题

- "怎么做业务员培训"
- "上线前的准备 checklist"

**新 Claude 的处理方式**：参考 02-development-plan.md 第 11-12 周的上线策略。

---

## 十一、常见误区提醒（给新 Claude）

新对话的 Claude 可能犯的错（请主动避免）：

1. ❌ 建议用 Hermes 的 memory/skill 系统 → ✅ 只用 Hermes 做 LLM 调用
2. ❌ 建议让 AI 自主规划多步操作 → ✅ 所有复杂操作必须是预定义 workflow
3. ❌ 建议让 AI 判断业务规则是否合理 → ✅ 规则是 Python 代码
4. ❌ 建议让 AI 自己计算数字做汇总 → ✅ 计算必须在工具里（SQL），AI 只转述
5. ❌ 建议用 DB 触发器实现 history 表 → ✅ 用代码显式写（便于关联审计上下文）
6. ❌ 建议物理删除数据 → ✅ 全局软删除
7. ❌ 建议在流水表加 contract_id 做对账 → ✅ 汇总对账，视图实现
8. ❌ 建议把工单/委托单价独立于合同 → ✅ 必须等于合同单价
9. ❌ 建议撮合合同算应收应付 → ✅ 撮合只算佣金
10. ❌ 脱离业务做数学计算 → ✅ 所有公式必须用真实业务场景验证
11. ❌ 建议现在就做复杂的长期记忆 → ✅ Phase 2 再考虑
12. ❌ 建议把 user_id 作为 LLM 可见参数 → ✅ 必须后端强制注入，防越权

---

## 十二、联系信息（发起人自填）

```
云服务器主机: [待购买]
云服务器备机: [待购买]
飞书应用 App ID: [待申请]
飞书应用 App Secret: [待申请]
GitHub 仓库: [待创建]
OpenAI Codex 账号: [已配置 / 待配置]
```

---

## 十三、给新 Claude 的初始指令建议

如果你用新对话 + 这份文档 + 配套 4 份文档来接续项目，建议的开场白：

```
我在做一个 ERP AI 对话系统的项目。请先仔细阅读我附上的这些文档：

1. 00-continuation-guide.md（会话延续指南 — 先看这个，最快了解全貌）
2. 01-project-blueprint.md（项目蓝本）
3. 02-development-plan.md（12 周开发计划）
4. schema.md（数据库设计 v0.6）
5. workflows.md（工作流定义 v0.1）

读完后请告诉我你理解的：
1. 项目目标
2. 当前阶段
3. 下一步要做什么

然后我再提具体问题。
```

这样新 Claude 会先建立完整的上下文，再开始帮你做事。

---

## 附录：文档版本说明

| 文档 | 版本 | 行数 | 状态 |
|-----|------|------|------|
| 00-continuation-guide.md | v2.5 | ~645 | ✅ 本文档 |
| 01-project-blueprint.md | v1.0 | ~1100 | ✅ 稳定 |
| 02-development-plan.md | v1.0 | ~1400 | ✅ 稳定 |
| schema.md | v0.9 | ~2990 | ✅ brand_aliases / product_aliases 完整设计 + AI 简称查询逻辑 |
| workflows.md | v0.2 | ~1110 | ✅ 新增 create_company + delete_alias |

---

*v2.5 - 2026-04-21 新增第六节 Claude vs Codex 工作流分工规则 + 文档头部警示（W0 后一律走 Codex 流程）*
*v2.4 - 2026-04-21 W0 Docker 骨架完成（26 个文件）+ 员工/角色架构盘点 + 下次会话 workflow 补全 TODO 清单*
*v2.3 - 2026-04-21 同步 schema v0.9 + product_aliases 完整设计（77 条简称）*
*v2.2 - 2026-04-21 同步 schema v0.8 + 品牌/型号/提货地主数据成果*
*v2.1 - 2026-04-21 补充客户档案清洗成果 + 简称自动生成机制 + create_company workflow*
*v2.0 - 2026-04-20 完整项目状态快照*
*通过这份文档，你随时可以从任何一次对话断点，无缝接回项目。*
