# ERP AI 对话系统 - 项目蓝本

> **版本**: v1.0
> **创建日期**: 2026-04-19
> **状态**: 设计定稿，待开发
> **文档目的**: 完整描述项目背景、架构、设计决策与实现要点。任何人（包括新一次对话的 Claude）读完此文档应能完全理解本项目。

---

## 1. 项目背景与目标

### 1.1 现状

公司现有 ERP 系统基于飞书多维表格构建，包含以下核心表：

- 采购合同 / 销售合同
- 提货工单 / 提货委托
- 流水记录
- 其他业务辅助表

现有工作模式：业务员通过飞书多维表格的 Web 界面进行录入、修改、删除操作。

### 1.2 痛点

1. **操作效率低**：多维表格界面对复杂业务流程支持不足，业务员需要手动维护多表之间的数据一致性
2. **易出错**：比如改销售合同数量时忘记对应修改提货工单和委托，导致数据对不上
3. **对账人工**：日常对账、问题筛查、异常追踪都靠人工，费时且易漏
4. **业务规则分散在人脑里**：新员工上手慢，老员工也会疏忽

### 1.3 目标

构建一个**AI 对话式 ERP 系统**，让业务员通过飞书与 AI 对话完成所有日常操作：

- **操作更简单**：自然语言描述需求，AI 理解并执行
- **错误更少**：系统在执行前强制校验业务规则，生成操作预览让用户确认
- **审计更强**：每一次操作都有完整追溯链路（对话→理解→方案→审批→执行→数据变更）
- **发现问题更及时**：AI 定时审计业务数据，异常自动生成待办，自愈自动关闭
- **查询更快**：业务员不用再去飞书表格里翻找，问 AI 即可获得准确答案

### 1.4 范围

**本期（MVP，12 周内完成）**：

- 合同、提货、流水的增删改查
- 核心复杂操作 workflow 化（约 10 个）
- 审批流与审计
- 业务查询与对账

**Phase 2（上线后按需开发）**：

- 利润分析
- 库存预警
- 跨会话长期记忆优化
- 软性异常检测（基于历史统计）

---

## 2. 用户与团队

### 2.1 使用者

10 名内部员工，分为以下角色：

| 角色 | 职责 | AI 使用场景 |
|------|------|------------|
| 销售业务员 | 对接客户，建销售合同，跟踪提货 | 建合同、改合同、查客户未提量、接收待办 |
| 采购业务员 | 对接上游，建采购合同 | 建采购合同、接提货委托、对接上游 |
| 单证 | 做提货工单、提货委托 | 建工单、建委托、处理裸工单待办 |
| 财务 | 流水、对账、开票 | 流水录入、日对账、拆主体 |
| 老板（你） | 总体把控 | 接收日报、审计报告、审批大单 |

### 2.2 权限模型

- 每个业务员只看/操作**与自己相关的数据**（自己负责的客户/合同/工单）
- 财务看全部财务相关数据
- 老板看全部
- 权限通过一张 `user_permissions` 表灵活配置（workflow 维度 + scope 过滤）

---

## 3. 技术架构

### 3.1 架构总览

```
┌──────────────────────────────────────────────┐
│          飞书 (用户入口 + 审批卡片)             │
└────────────────┬─────────────────────────────┘
                 │ 事件订阅 / 卡片回调
┌────────────────▼─────────────────────────────┐
│    ① 飞书 Gateway 服务                        │
│    - 消息收发 / 卡片渲染 / 身份映射            │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│    ② Agent 编排层                             │
│    - 会话状态管理 / LLM 调用 / 工具路由         │
│    - LLM 后端: Hermes (接 OpenAI 会员)         │
└────────────────┬─────────────────────────────┘
                 │ MCP / Function Call
┌────────────────▼─────────────────────────────┐
│    ③ MCP 工具层                               │
│    - 查询工具 / 模糊匹配 / Workflow 触发        │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│    ④ Workflow 引擎 + 规则引擎                 │
│    - Plan 生成 / 约束校验 / 事务执行            │
└────────────────┬─────────────────────────────┘
                 │
      ┌──────────┼──────────┐
      ▼          ▼          ▼
  ┌─────────┐ ┌─────────┐ ┌─────────┐
  │规则引擎  │ │审批引擎  │ │审计引擎  │
  └────┬────┘ └────┬────┘ └────┬────┘
       │           │           │
       └───────────┼───────────┘
                   ▼
         ┌─────────────────┐
         │   PostgreSQL    │
         │ 业务数据+历史表  │
         │ +审计+对话       │
         └─────────────────┘
```

### 3.2 技术选型（已锁定）

| 层 | 选择 | 理由 |
|----|------|------|
| 编程语言 | Python 3.11+ | 飞书 SDK 成熟、Hermes 同生态、AI 开发主流 |
| Web 框架 | FastAPI | 异步、类型安全、自动文档 |
| 数据库 | PostgreSQL 16 + pg_trgm | 你已决定；trgm 做模糊匹配 |
| ORM | SQLAlchemy 2.0 + Alembic | ORM 主流，迁移管理成熟 |
| LLM 后端 | Hermes → OpenAI (GPT) | 节省会员费；Hermes 只做调用中转 |
| 任务调度 | APScheduler | 单机简单、无需 Redis |
| 容器化 | Docker + docker-compose | 方便迁移和备份 |
| 飞书 | 官方开放平台 SDK + CLI | 官方支持 |
| 测试 | pytest | Python 测试主流 |
| 版本控制 | Git（私有仓库） | 基础设施 |

### 3.3 部署方案

**主机**：云服务器 4C8G Ubuntu 22.04
**备机**：同配置第二台，冷备（主机挂了切 DNS）
**备份**：PG 每日 dump 至对象存储（7 天保留）
**容器化**：所有服务 docker-compose 启动
**外网**：云服务器有公网 IP，飞书 webhook 直接回调

### 3.4 为什么 Hermes 只做 LLM 后端

Hermes 是为 personal agent 设计的，假设"单用户"场景。它的 memory、skill 自完善、gateway 不适合企业多用户：

- Memory 会把 10 个业务员的对话混在一起形成一个扭曲的人格画像
- Skill 自完善在企业场景是负资产（自由度过高，可审计性差）
- Gateway 不支持飞书

**我们的用法**：只把 Hermes 作为"LLM 调用的代理层"，利用它帮我们走 OpenAI 会员额度。所有会话、记忆、用户管理全部自己用 PG 实现。

---

## 4. 核心设计哲学

下面这些原则贯穿整个系统。**任何功能设计与实现决策都必须遵循**。

### 4.1 AI 是翻译官，不是决策者

AI 的职责：
- 理解自然语言意图
- 选择合适的 workflow 或查询工具
- 把工具返回转成自然语言
- 对模糊输入做澄清

AI 绝不做：
- 业务判断（比如"该改成多少合理"）
- 多步自主规划
- 直接写数据库
- 对未查到的数据做推测

### 4.2 写操作必须经过 Plan

所有写操作都是两阶段的：

```
阶段 1 (propose):  AI 生成 Plan（包含操作列表 + 校验结果 + 影响分析）
                   ↓
阶段 2 (confirm):  用户看预览后确认 → 审批 → 事务执行
```

AI 在阶段 1 调用 `propose_*` 工具，返回 Plan。阶段 2 必须由用户在飞书卡片上点击确认。这保证了即使 AI 理解错，数据也不会被破坏。

### 4.3 业务约束必须代码化

所有硬业务规则都是 Python 代码，不让 LLM 判断：

- 提货不能超合同
- 审批合规性
- 数据时间线合理性
- 孤儿记录检测

LLM 不参与判断"这次改动是否合理"，它只负责把规则违反情况用自然语言解释给用户。

### 4.4 查询必须有证据

所有查询返回的数字、编号、日期都必须是工具直接返回的原始数据。AI 不做计算、不做汇总、不编造。

幻觉防护三道防线：
1. Prompt 明确禁止
2. 结构化输出 + 后置代码校验（AI 引用的合同号必须在原始数据里）
3. 原始数据附带展示给用户

### 4.5 审计必须形成闭环

每个异常从"发现"到"解决"都有清晰记录：
- 异常发现 → 入 `pending_issues` 表，分配负责人
- 异常持续 → 每次审计更新 last_seen_at
- 异常消失 → AI 自动标记 resolved（不靠用户手动报告）

### 4.6 每次 AI 操作都必须可回溯

完整 ID 链：

```
conversation_id → plan_id → approval_record_ids → audit_log_id → history_record_ids
```

任意一端可以回溯到起点：看到一条数据异常，能找到是哪次对话触发的、当时业务员说了什么、AI 怎么理解的、谁审批的。

### 4.7 用户身份强制注入

AI 永远不能自己选"我以谁的身份执行操作"。每次工具调用，当前用户 ID 由后端强制注入，LLM 传的任何 user_id 参数都会被覆盖。这是防越权的硬保证。

---

## 5. 数据模型

### 5.1 表分类

数据库表分为五类：

1. **业务表**：contracts, delivery_orders, delivery_delegations, transactions, companies, products
2. **主数据表**：users, company_aliases, product_aliases, audit_rule_configs, approval_rules, user_permissions
3. **审计表**（只允许 INSERT + SELECT，PG 权限控制）：audit_logs, change_proposals, approval_records, contracts_history, delivery_orders_history 等所有 history 表
4. **AI 运行表**：conversations, messages, pending_issues
5. **辅助表**：holidays, leave_records（审批转移用）

### 5.2 所有表通用字段

```sql
id              uuid primary key default gen_random_uuid(),
created_at      timestamptz not null default now(),
updated_at      timestamptz not null default now(),
version         int not null default 1,        -- 乐观锁
created_by      uuid references users(id),
updated_by      uuid references users(id)
```

### 5.3 核心业务表示例

```sql
-- 合同表
CREATE TABLE contracts (
  id uuid PRIMARY KEY,
  contract_number varchar(50) UNIQUE NOT NULL,
  contract_type varchar(20) NOT NULL,  -- 'sales' | 'purchase'
  subject_company varchar(100) NOT NULL,  -- 本方主体 (A 公司 / B 公司)
  counterparty_id uuid REFERENCES companies(id),  -- 对方公司
  brand_id uuid REFERENCES brands(id),
  product_id uuid REFERENCES products(id),
  quantity decimal(12,3) NOT NULL,
  unit_price decimal(10,2) NOT NULL,
  total_amount decimal(14,2) NOT NULL,
  signed_at date NOT NULL,
  valid_from date NOT NULL,
  valid_to date NOT NULL,
  status varchar(20) NOT NULL,  -- 'active' | 'completed' | 'cancelled'
  owner_user_id uuid REFERENCES users(id),  -- 负责人
  -- 通用字段
  created_at, updated_at, version, created_by, updated_by
);

CREATE INDEX idx_contracts_counterparty ON contracts(counterparty_id);
CREATE INDEX idx_contracts_owner ON contracts(owner_user_id);
CREATE INDEX idx_contracts_status ON contracts(status);
```

### 5.4 历史表（所有业务表都有）

```sql
CREATE TABLE contracts_history (
  id uuid PRIMARY KEY,
  record_id uuid NOT NULL,  -- 指向原 contracts.id
  op_type varchar(10) NOT NULL,  -- 'insert' | 'update' | 'delete'
  before_snapshot jsonb,  -- 操作前完整行
  after_snapshot jsonb,  -- 操作后完整行
  changed_fields text[],  -- 变更了哪些字段
  changed_at timestamptz NOT NULL,
  changed_by uuid REFERENCES users(id),
  audit_log_id uuid REFERENCES audit_logs(id)  -- 关联到审计日志
);

CREATE INDEX idx_contracts_history_record ON contracts_history(record_id, changed_at DESC);
```

**原则**：每次业务表的 INSERT/UPDATE/DELETE 都必须在同事务内向 history 表写一条。由 `ProposalExecutor` 显式写（不用触发器，便于关联审计上下文）。

### 5.5 审计核心表

```sql
-- 操作审计
CREATE TABLE audit_logs (
  id uuid PRIMARY KEY,
  plan_id uuid REFERENCES change_proposals(id),
  conversation_id uuid REFERENCES conversations(id),
  message_id uuid REFERENCES messages(id),  -- 触发操作的用户消息
  workflow_name varchar(100),
  workflow_version varchar(20),
  user_id uuid REFERENCES users(id),
  operations jsonb NOT NULL,  -- 执行的操作列表
  status varchar(20) NOT NULL,  -- 'success' | 'failed' | 'rolled_back'
  error_message text,
  executed_at timestamptz NOT NULL,
  duration_ms int
);

-- 操作提案
CREATE TABLE change_proposals (
  id uuid PRIMARY KEY,
  workflow_name varchar(100) NOT NULL,
  workflow_version varchar(20) NOT NULL,
  params jsonb NOT NULL,
  operations jsonb NOT NULL,
  violations jsonb,
  required_approvers jsonb,
  status varchar(20) NOT NULL,
  -- 'draft' | 'pending_confirm' | 'pending_approval'
  -- | 'executing' | 'completed' | 'cancelled' | 'rejected' | 'failed'
  created_by uuid REFERENCES users(id),
  conversation_id uuid REFERENCES conversations(id),
  confirmed_at timestamptz,
  confirmed_by uuid,
  executed_at timestamptz,
  audit_log_id uuid REFERENCES audit_logs(id)
);

-- 审批记录
CREATE TABLE approval_records (
  id uuid PRIMARY KEY,
  plan_id uuid NOT NULL REFERENCES change_proposals(id),
  approver_user_id uuid NOT NULL REFERENCES users(id),
  approver_role varchar(50),
  sequence int NOT NULL,  -- 第几级审批
  decision varchar(20),  -- 'approved' | 'rejected' | 'delegated' | 'pending'
  comment text,
  decided_at timestamptz,
  card_message_id varchar(100),  -- 飞书卡片消息 ID
  original_approver_id uuid  -- 如果转移了，原审批人
);
```

### 5.6 AI 运行表

```sql
-- 对话
CREATE TABLE conversations (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id),
  started_at timestamptz NOT NULL,
  last_activity_at timestamptz NOT NULL,
  ended_at timestamptz,
  title varchar(200),  -- AI 自动总结主题
  summary text,  -- 长对话压缩后的摘要
  message_count int DEFAULT 0
);

CREATE INDEX idx_conversations_user_activity
  ON conversations(user_id, last_activity_at DESC);

-- 消息
CREATE TABLE messages (
  id uuid PRIMARY KEY,
  conversation_id uuid NOT NULL REFERENCES conversations(id),
  role varchar(20) NOT NULL,  -- 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'system'
  content jsonb NOT NULL,
  tool_name varchar(100),
  tool_input jsonb,
  tool_output jsonb,
  created_at timestamptz NOT NULL
);

CREATE INDEX idx_messages_conversation
  ON messages(conversation_id, created_at);

-- 待办异常
CREATE TABLE pending_issues (
  id uuid PRIMARY KEY,
  rule_name varchar(100) NOT NULL,
  issue_key varchar(200) NOT NULL UNIQUE,  -- 唯一标识，去重用
  category varchar(50),
  severity varchar(20),
  title varchar(300) NOT NULL,
  description text,
  affected_records jsonb,
  owner_user_ids uuid[] NOT NULL,
  status varchar(20) NOT NULL,  -- 'open' | 'resolved' | 'manual_override'
  first_detected_at timestamptz NOT NULL,
  last_seen_at timestamptz NOT NULL,
  resolved_at timestamptz,
  resolution_method varchar(30),  -- 'auto_resolved' | 'manual_override'
  detection_count int DEFAULT 1
);

CREATE INDEX idx_pending_issues_owner_status
  ON pending_issues USING gin(owner_user_ids);
CREATE INDEX idx_pending_issues_status ON pending_issues(status, last_seen_at);
```

### 5.7 模糊匹配表

```sql
CREATE TABLE company_aliases (
  id uuid PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES companies(id),
  alias varchar(100) NOT NULL,
  alias_type varchar(30),  -- 'common' | 'formal' | 'english' | 'user_specific'
  specific_user_id uuid REFERENCES users(id),  -- 仅对某用户有效
  confidence decimal(3,2) DEFAULT 1.0,
  source varchar(30),  -- 'manual' | 'disambiguation' | 'promoted'
  created_at timestamptz
);

CREATE INDEX idx_company_aliases_alias ON company_aliases(alias);
CREATE INDEX idx_company_aliases_trgm
  ON company_aliases USING gin(alias gin_trgm_ops);
```

### 5.8 配置表

```sql
-- 审计规则配置
CREATE TABLE audit_rule_configs (
  id uuid PRIMARY KEY,
  rule_name varchar(100) UNIQUE NOT NULL,
  cron_expression varchar(50) NOT NULL,  -- APScheduler 格式
  enabled boolean DEFAULT true,
  config_json jsonb,
  last_run_at timestamptz,
  last_run_status varchar(20)
);

-- 审批规则
CREATE TABLE approval_rules (
  id uuid PRIMARY KEY,
  name varchar(100) NOT NULL,
  workflow_name varchar(100) NOT NULL,
  match_condition jsonb,  -- 匹配条件 (e.g. amount > 10000)
  approvers jsonb,  -- 审批人列表 (角色/角色+条件)
  priority int DEFAULT 0,
  enabled boolean DEFAULT true
);

-- 用户权限
CREATE TABLE user_permissions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id),
  workflow_name varchar(100) NOT NULL,
  scope_filter jsonb,  -- e.g. {"owner_user_id": "$user_id"}
  allowed boolean DEFAULT true
);
```

---

## 6. 核心子系统设计

### 6.1 Workflow 引擎

**职责**：定义和执行业务操作流程。每个 Workflow 是一个 Python 类，包含前置检查、Plan 生成、事务执行、事后核验。

**数据结构**：

```python
@dataclass
class ChangeOperation:
    op_type: Literal["insert", "update", "delete"]
    table: str
    record_id: Optional[str]
    before: Optional[dict]
    after: Optional[dict]

@dataclass
class ValidationViolation:
    rule_name: str
    severity: Literal["error", "warning"]
    message: str
    affected_records: list[dict]

@dataclass
class Plan:
    id: str
    workflow_name: str
    workflow_version: str
    params: dict
    operations: list[ChangeOperation]
    violations: list[ValidationViolation]
    required_approvers: list[dict]
    status: str  # 见 change_proposals.status 枚举
    created_by: str
    conversation_id: str
    created_at: datetime
```

**Workflow 基类**：

```python
class BaseWorkflow:
    name: str
    version: str
    required_params: list[str]
    description: str

    def validate_params(self, params: dict) -> None:
        """校验参数完整性"""

    def check_permissions(self, user_id: str, params: dict, db) -> None:
        """权限检查，失败抛异常"""

    def plan(self, params: dict, user_id: str, db) -> Plan:
        """生成操作计划，跑规则校验"""

    def execute(self, plan: Plan, db) -> AuditLog:
        """在事务内执行 plan"""

    def verify_post_execution(self, plan: Plan, db) -> None:
        """事后核验，失败抛异常（会触发事务回滚）"""
```

**初始 Workflow 清单**（需你确认具体细节）：

1. `create_sales_contract` - 新建销售合同
2. `create_purchase_contract` - 新建采购合同
3. `update_contract_quantity` - 修改合同数量
4. `update_contract_price` - 修改合同单价
5. `cancel_contract` - 作废合同
6. `create_delivery_order` - 新建提货工单
7. `create_delivery_delegation` - 新建提货委托
8. `update_delivery_quantity` - 修改提货数量
9. `split_executed_contract` - 拆分已执行合同（换主体）
10. `record_transaction` - 录入流水

### 6.2 规则引擎

**职责**：定义所有业务约束规则。Plan 生成时、执行前、执行后都会跑相关规则。

**规则基类**：

```python
class BaseRule:
    name: str
    applies_to_tables: list[str]  # 哪些表的变更触发此规则

    def validate(self, plan: Plan, db) -> list[ValidationViolation]:
        """返回违规列表"""
```

**初始规则清单**：

1. `delivery_not_exceed_contract` - 提货总量不超合同
2. `delivery_order_matches_delegation` - 工单数量 = 对应委托数量
3. `sales_purchase_quantity_balance` - 销售已提 ≤ 采购已提
4. `contract_date_range_valid` - 提货日期在合同执行期内
5. `no_orphan_delivery_order` - 提货工单必须关联销售合同
6. `no_orphan_delivery_delegation` - 提货委托必须关联采购合同
7. `amount_consistency` - 总金额 = 数量 × 单价
8. `status_transition_valid` - 状态流转合法（不能从 cancelled 回到 active）

### 6.3 审计引擎

**职责**：定时扫描数据，发现异常生成/更新/关闭 `pending_issues`。

**AuditRule 基类**：

```python
class AuditRule:
    name: str
    category: str
    severity: str

    def check(self, db) -> list[Violation]:
        """扫描数据，返回当前所有违规"""

    def determine_owner(self, violation, db) -> list[str]:
        """根据违规确定负责人 user_id 列表"""

    def generate_issue_key(self, violation) -> str:
        """生成唯一 key 用于去重"""

    def get_title(self, violation) -> str:
        """生成人类可读的标题"""
```

**核心自愈逻辑**：

```python
def run_audit_rule(rule: AuditRule):
    with db.transaction():
        current_detected_keys = set()
        violations = rule.check(db)

        for v in violations:
            key = rule.generate_issue_key(v)
            current_detected_keys.add(key)

            existing = db.query(PendingIssue)\
                .filter_by(issue_key=key, status='open')\
                .first()

            if existing:
                existing.last_seen_at = now
                existing.detection_count += 1
            else:
                db.add(PendingIssue(
                    rule_name=rule.name,
                    issue_key=key,
                    ... # 其他字段
                ))

        # 自愈：之前 open 但这次没发现的 → 标记 resolved
        previously_open = db.query(PendingIssue)\
            .filter_by(rule_name=rule.name, status='open')\
            .filter(PendingIssue.issue_key.notin_(current_detected_keys))\
            .all()

        for issue in previously_open:
            issue.status = 'resolved'
            issue.resolved_at = now
            issue.resolution_method = 'auto_resolved'

        db.commit()

    # 同步到飞书多维表格（另起协程）
    sync_pending_issues_to_feishu_bitable()
```

**初始审计规则清单**：

1. `bare_delivery_order_check` - 裸工单（工单无对应委托）
   - 频率：每小时
   - 负责人：工单创建人（单证）
2. `bare_delivery_delegation_check` - 裸委托
   - 频率：每小时
   - 负责人：委托创建人
3. `daily_sales_purchase_balance` - 销售采购日对账
   - 频率：每天凌晨 3 点
   - 负责人：财务 + 相关业务员
4. `daily_transaction_contract_balance` - 流水-合同对账
   - 频率：每天凌晨 3 点
   - 负责人：财务
5. `orphan_records_check` - 孤儿记录
   - 频率：每 6 小时
   - 负责人：相关业务员
6. `approval_compliance_check` - 审批合规性
   - 频率：每天
   - 负责人：老板
7. `contract_quantity_conservation` - 合同数量守恒
   - 频率：每小时
   - 负责人：合同负责人
8. `date_timeline_consistency` - 时间线合理性
   - 频率：每天
   - 负责人：创建人

### 6.4 查询系统

**职责**：业务数据查询，覆盖日常 80% 的"问答"需求。

**三层工具架构**：

**第一层：基础查询（Low-level）**
```python
# 工具示例
@tool
def search_contracts(
    contract_type: Optional[str] = None,
    customer_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    status: Optional[str] = None,
    signed_from: Optional[date] = None,
    signed_to: Optional[date] = None,
    valid_from: Optional[date] = None,
    valid_to: Optional[date] = None,
    _current_user_id: str,  # 强制注入，过滤用户可见范围
) -> list[ContractRecord]:
    """返回合同列表的原始记录"""
```

其他基础工具：
- `get_contract_detail` - 合同详情（含关联提货）
- `search_deliveries` - 查提货
- `search_transactions` - 查流水
- `search_pending_quantity` - 查未提量（核心工具）
- `fuzzy_match_company` / `fuzzy_match_brand` / `fuzzy_match_product` - 模糊匹配
- `get_my_pending_issues` - 我的待办

**第二层：业务语义查询（Business-Semantic）**

```python
@tool
def query_customer_pending_summary(
    customer_id: str,
    contract_type: str = "sales",  # 业务默认值
    include_completed: bool = False,
    _current_user_id: str,
) -> CustomerPendingSummary:
    """返回结构化的客户未提量汇总（按品牌/按合同分组）"""
```

其他语义工具：
- `query_brand_pending_summary`
- `query_monthly_statistics` - 月度业务统计
- `query_user_performance` - 业务员业绩

**第三层**：暂不实现。

**幻觉防护**：

```python
def verify_ai_response(ai_response: dict, tool_results: list[dict]):
    """校验 AI 回答里引用的数据都在原始工具返回中"""
    for evidence in ai_response.get('evidence', []):
        record_id = evidence['contract_number']
        found = find_in_results(tool_results, contract_number=record_id)
        if not found:
            raise HallucinationDetected(f"AI 引用了不存在的合同: {record_id}")

        for field in ['signed_quantity', 'delivered_quantity', 'unit_price', 'valid_until']:
            if evidence.get(field) != found.get(field):
                raise HallucinationDetected(
                    f"字段 {field} 不一致: AI={evidence[field]} 原始={found[field]}"
                )
```

**业务默认值规则**（需你完善成清单）：

- "还剩多少没提" / "未提货" → 默认销售合同
- "这个月" → 当前自然月
- "最近" → 近 30 天
- "某客户 / 某品牌" → 模糊匹配命中 1 条自动用，多条让用户选
- "签了多少" → 模糊，必须反问（销售还是采购）

### 6.5 审批引擎

**职责**：判断 Plan 是否需审批、走几级、审批人是谁、下发卡片、收集结果。

**审批规则示例**（存在 `approval_rules` 表）：

```yaml
- name: "修改合同默认审批"
  workflow_name: "update_contract_quantity"
  match_condition: {}  # 无条件匹配
  approvers:
    - role: "contract_owner"
      sequence: 1
    - role: "department_manager"
      sequence: 2
      condition: "abs(changes.quantity.delta) > 100"
```

**审批人动态解析**（解决请假转移）：

```python
def resolve_approver(role: str, date: date, context: dict) -> str:
    # 1. 查角色当前主责人
    primary = lookup_role_holder(role, date)

    # 2. 检查是否请假
    if is_on_leave(primary, date):
        # 查委托人
        delegate = lookup_leave_delegate(primary, date)
        if delegate and not is_on_leave(delegate, date):
            return delegate
        # 委托人也不在，升级到上级
        return lookup_upper_manager(primary)

    return primary
```

**审批流程**：

```
Plan 生成 → 匹配审批规则 → 解析审批人
         → 下发飞书卡片给第 1 级
         → 第 1 级同意 → 下发第 2 级
         → 全部同意 → 执行 Plan
         → 任意拒绝 → Plan 状态变 rejected
         → 超时（2 小时）→ 自动升级上级 + 告警
```

### 6.6 会话管理

**核心策略**：

- 30 分钟无活动 → 自动开新 session
- 用户发 "新对话" / "/new" → 强制开新
- 每个 session 内消息全量存
- 超过 20 轮的对话，自动压缩更早部分为摘要

**AI 上下文拼装**：

```
[system prompt]
  基础角色设定
  + 当前用户信息 (张三, 销售业务员, 负责 X/Y/Z 客户)
  + 可用工具描述
  + 业务默认值规则
  + 澄清原则

[如果有] 历史摘要: "之前对话中用户查询了美远贸易的未提量..."

[最近 N 轮消息，按时间顺序]
  user: "三房的呢？"  (追问)
  ... 

[当前消息]
  user: "导出成 excel"
```

### 6.7 飞书 Gateway

**职责**：
- 订阅飞书事件（消息、卡片回调）
- 用户身份映射（open_id → user_id）
- 消息路由到 Agent
- 把 Plan 预览渲染成飞书交互式卡片
- 把待办同步到飞书多维表格（每 5 分钟）

**飞书卡片示例（Plan 预览）**：

```json
{
  "header": { "title": "操作预览 - 修改合同数量" },
  "elements": [
    { "tag": "div", "text": "合同 C20260312 数量变更" },
    { "tag": "div", "text": "• 美远贸易 · 三房 302" },
    { "tag": "div", "text": "• 数量: 330 吨 → 200 吨" },
    { "tag": "div", "text": "• 已提货: 150 吨（不超过新数量）" },
    { "tag": "hr" },
    { "tag": "div", "text": "⚠️ 需要二级审批：部门主管" },
    { "tag": "action", "actions": [
      { "tag": "button", "text": "确认执行", "type": "primary", "value": {...} },
      { "tag": "button", "text": "取消", "type": "default" }
    ]}
  ]
}
```

---

## 7. AI Prompt 设计

### 7.1 System Prompt 骨架

```
你是公司 ERP 系统的 AI 助手。你帮助业务员完成业务操作和数据查询。

## 你的职责

1. 理解业务员用自然语言描述的需求
2. 选择合适的 workflow 或查询工具
3. 把工具的结果用清晰的自然语言展示给用户
4. 对模糊的表达做澄清
5. 写操作永远先生成 Plan 让用户确认

## 当前用户

- 姓名: {user_name}
- 角色: {user_role}
- 飞书 ID: {user_id}
- 负责的客户: {user_customers}
- 权限范围: {user_permissions}

## 核心规则（严格遵守）

1. **你不做业务判断**。不判断"这次改动合不合理"、"值不值得"这类主观判断。
2. **你不计算数字**。所有数字来自工具返回，不自己加减乘除。
3. **你不编造数据**。合同号、客户名、数字、日期必须来自工具返回。
4. **写操作必须先 propose 再 confirm**。生成 Plan → 展示预览 → 用户确认 → 才执行。
5. **模糊表达先澄清**。模糊公司名/品牌名先调 fuzzy_match，候选多条必须让用户选。
6. **查询时有业务默认值的直接用并标注**，没有默认值的才反问。

## 业务默认值

{business_defaults}  # 从配置表动态读取

## 你可用的工具

{tool_descriptions}

## 禁止事项

- 禁止说"大约"、"差不多"、"估计"
- 禁止对没查到的数据做推测
- 禁止使用 user_id 参数（后端会自动注入当前用户）
- 禁止跳过 Plan 确认直接写数据

## 回答格式

查询类回答:
"<结论>: <具体数字>
详情:
- <记录 1>
- <记录 2>
数据来源: <工具名>"

写操作类回答:
"我将要执行:
- <操作 1>
- <操作 2>
涉及约束:
- ✅/⚠️ <规则> - <说明>
审批: <无需审批 / 需要 X 审批>
确认执行吗? [按钮]"
```

### 7.2 关键 Prompt 调优点

- Few-shot 示例（5-10 个典型对话）
- 错误示范（反面教材）
- 每个工具的详细使用说明
- 常见问法与意图映射

这些都需要你列的 **6 份知识资产文档**作为原料。

---

## 8. 安全设计

### 8.1 权限控制

- **用户身份**：飞书 open_id 映射到内部 user_id，所有请求必须有 user_id
- **工具级权限**：每个 MCP 工具都检查 user_id 是否允许调用（读取 `user_permissions` 表）
- **数据级权限**：查询工具自动加 `owner_user_id = :user_id OR user_role = 'admin'` 过滤
- **工作流级权限**：复杂 workflow 在 `plan()` 里做额外校验

### 8.2 AI 越权防护

- **user_id 强制注入**：后端在调用工具前，把参数里的 user_id 强制替换为当前用户
- **工具白名单**：system prompt 只告诉 AI 它能调哪些工具；尝试调用未知工具被拒绝
- **审计告警**：AI 尝试调用未授权工具 / 生成明显违规 Plan → 记录并告警

### 8.3 数据保护

- **审计表只写**：audit_logs、change_proposals、approval_records、history 表在 PG 权限层只允许 INSERT 和 SELECT
- **备份**：PG 每日 dump 到对象存储
- **容灾**：备机冷备，主机挂了 DNS 切换

### 8.4 注入防护

- **SQL**：用 ORM 参数化查询，禁止字符串拼 SQL
- **Prompt**：用户输入不直接拼到 prompt 里；AI 只看用户消息是"数据"不是"指令"
- **Webhook**：飞书回调做签名验证

---

## 9. 必须完成的 6 份知识资产文档

这些文档是你需要自己（或和懂业务的同事一起）完成的。它们不是代码能生成的，是你公司业务知识的数字化沉淀。**没有这些，codex 无法真正干活**。

### 9.1 schema.md（业务表结构定义）

内容：每张业务表的字段、类型、含义、约束、关联关系。

示例：
```
## 合同表 contracts

| 字段名 | 类型 | 必填 | 含义 | 约束 | 说明 |
|-------|------|------|------|------|------|
| contract_number | varchar(50) | Y | 合同编号 | UNIQUE | 格式：C{YYYYMMDD}{NNN} |
| contract_type | enum | Y | 合同类型 | sales/purchase | |
| subject_company | varchar(100) | Y | 本方主体 | A公司/B公司 | 用于拆票 |
...
```

### 9.2 workflows.md（复杂操作 Workflow 定义）

内容：10 个 workflow 的名字、参数、前置条件、原子操作序列、异常分支。

示例：
```
## split_executed_contract 拆分已执行合同

用途: 财务月底需要换主体时，拆分合同并重建提货链

参数:
- original_contract_id (必填)
- split_ratios (必填, 例 [{"subject": "A", "ratio": 0.5}, {"subject": "B", "ratio": 0.5}])
- reason (必填)

前置条件:
- 原合同状态 = completed
- 原合同有关联提货记录
- 新主体在白名单

原子操作序列:
1. 作废原合同 (status=cancelled)
2. 为每个拆分比例创建新合同
3. 重建提货工单和委托

异常分支:
- 提货链按比例拆不整除 → 暂停，让用户选处理方式
- ...
```

### 9.3 aliases.xlsx（公司/品牌/型号简称表）

内容：公司、品牌、型号的常用简称，三列：`正式名`、`简称`、`备注`。

**初始版本覆盖 50 个最常用客户 + 所有品牌 + 主要型号即可。**

### 9.4 audit-rules.md（审计规则清单）

内容：所有审计规则的定义、触发条件、负责人归属、严重等级、运行频率。

示例：
```
## bare_delivery_order_check 裸工单检测

触发: 提货工单 status='active' 但找不到对应的提货委托
运行频率: 每小时 (cron: 0 * * * *)
严重等级: medium
负责人: delivery_order.created_by
Title 生成: "裸工单 {order_number} 无对应委托"
自愈条件: 下次扫描时已找到对应委托
```

### 9.5 queries.md（日常查询场景清单）

内容：业务员/财务/老板日常会问的 30-50 个问题，按维度分类。

示例：
```
## 客户维度

Q: 某某公司还有多少没提？
- 意图: 查客户未提量
- 业务默认: 销售合同
- 工具: query_customer_pending_summary
- 示例: "美远还剩多少没提"

Q: 某某公司这个月签了多少？
- 意图: 查客户本月签约量
- 业务默认: 必须反问（销售 or 采购）
- 工具: search_contracts + 汇总
...
```

### 9.6 business-defaults.md（业务默认值规则）

内容：所有可能模糊的表达及其默认解读。

示例：
```
| 表达 | 默认解读 | 是否反问 | 备注 |
|------|---------|---------|------|
| 还剩多少没提 | 销售合同 | 否，在回答中标注 | 95% 场景 |
| 签了多少 | 模糊 | 必须反问 | 销售/采购都常见 |
| 这个月 | 当前自然月 | 否 | |
| 最近 | 近 30 天 | 否 | |
| 老王 | 模糊匹配用户 | 多人同名则反问 | |
```

---

## 10. 风险与应对

| 风险 | 可能性 | 影响 | 应对 |
|------|--------|------|------|
| AI 意图识别错误 | 中 | 高 | Plan 预览 + 二次确认；意图歧义必须反问 |
| AI 幻觉数据 | 中 | 高 | 结构化输出 + 后置校验 + 原始数据展示 |
| 业务员不配合使用 | 中 | 高 | 老系统并行 2 周；老板推动；AI 日报展示使用量 |
| Workflow 定义不完整 | 高 | 中 | 保留管理员手动兜底；持续补充 |
| 审计规则误报 | 高 | 低 | 自愈机制降低骚扰；规则可配置关闭 |
| 主机故障 | 低 | 高 | 备机冷备 + 每日备份 |
| 飞书 API 限流 / 故障 | 低 | 中 | 重试机制 + 降级为纯文本消息 |
| Hermes 更新破坏性变更 | 中 | 中 | 锁定版本，升级前全量回归 |
| LLM 服务中断 | 低 | 高 | 告警 + 人工降级到旧系统 |

---

## 11. 后续扩展（Phase 2）

上线稳定运行 3 个月后再考虑：

1. **跨会话长期记忆**：业务员偏好学习（默认查销售/采购等）
2. **软性异常检测**：基于统计的异常（量突增、价偏离）
3. **利润分析**：单合同利润 + 客户/品类维度
4. **库存预警**：基于提货节奏预测缺口
5. **智能建议**：主动提醒"你有 3 个合同本周到期"
6. **客户画像**：自动生成客户交易习惯报告
7. **语音输入**：业务员在车上也能用

**Phase 2 的总原则仍是**：AI 是分析师/助手，不是决策者。

---

## 附录 A：术语表

| 术语 | 定义 |
|------|------|
| Workflow | 预定义的业务操作流程 |
| Plan | Workflow 生成的操作方案（未执行） |
| Proposal | Plan 的别名（在 DB 层叫 change_proposal） |
| Operation | Plan 里的一个原子操作（insert/update/delete 某条记录） |
| History 表 | 业务表对应的变更历史表 |
| Audit Log | 每次执行 Plan 的审计记录 |
| Pending Issue | 待办异常（审计发现的问题） |
| Conversation | 一次连续对话 |
| Session | = Conversation |
| Hermes | LLM 调用代理（本项目只用它的 LLM 调用能力） |

## 附录 B：文档索引

- 本文件：**01-project-blueprint.md** - 项目蓝本
- **02-development-plan.md** - 12 周开发计划
- 待你完成的知识资产：
  - schema.md
  - workflows.md
  - aliases.xlsx
  - audit-rules.md
  - queries.md
  - business-defaults.md

---

*文档结束 - v1.0*
