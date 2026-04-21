# ERP AI 对话系统 - 12 周开发计划

> **配套文档**: 01-project-blueprint.md
> **开发方式**: 你（产品 / PM）+ OpenAI Codex（执行）+ Claude（Review）
> **每周投入**: 你约 3-5 小时 + Codex 自主开发

---

## 开发工作流（必读）

### 标准任务流程

```
1. 你阅读本文档本周任务部分，理解目标
2. 打开 Codex，把本周"codex 任务模板"复制给它
3. Codex 开发 + 自测 + 生成产物
4. Codex 把生成的文件路径 / 代码贴回来给你
5. 你执行"你的验收动作"部分，判断是否通过
6. 若有代码疑虑，把 Codex 的产出 + 本周任务描述发给 Claude 审查
7. 根据 Claude 反馈让 Codex 修改，再验收
8. 通过后 git commit + 打 tag
```

### 项目根目录放置 AGENTS.md

在项目根目录创建 `AGENTS.md`，内容：

```markdown
# 项目开发规范

## 技术栈
- Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16
- 测试: pytest
- Lint: ruff + black
- Type check: mypy (strict mode for 核心模块)

## 核心原则
1. 所有数据库修改必须在事务内 (async with session.begin():)
2. 所有写操作必须产生 audit_log 记录
3. 所有业务表的 INSERT/UPDATE/DELETE 必须同事务写对应 history 表
4. 所有 MCP 工具必须强制注入 current_user_id（不信任 LLM 传的值）
5. 所有向 user 展示的数据必须来自工具直接返回，不得由 AI 计算

## 开发纪律
1. 每个新模块必须有 README.md
2. 每个 public 函数必须有 docstring
3. 测试覆盖率: 核心业务逻辑 > 80%
4. 提交前必须跑 pytest 且全部通过
5. 代码必须过 ruff check 和 mypy 无 error

## 禁止事项
- 禁止硬编码业务常量
- 禁止在 AI prompt 里用 f-string 拼用户输入
- 禁止在业务逻辑里用 os.system / eval / exec
- 禁止跳过测试提交
- 禁止用 DB 触发器实现 history 表写入
```

### 给 Claude 的审查请求模板

```
请帮我审查以下代码（来自我的 ERP AI 项目的第 X 周任务）。

本周目标: [从本文档复制]
Codex 产出: [贴代码]

关注点:
1. 是否符合项目蓝本里的核心原则？
2. 是否有 SQL 注入、权限绕过等安全隐患？
3. 事务边界是否正确？
4. 测试是否覆盖了边界情况？
```

---

## 第 0 周：准备工作（不写代码）

### 你的任务清单

**基础设施**
- [ ] 购买云服务器主机 + 备机（阿里云/腾讯云 4C8G Ubuntu 22.04）
- [ ] 配置 SSH 密钥登录
- [ ] 两台机器安装 Docker + docker-compose
- [ ] 购买对象存储（用于 PG 备份）

**飞书配置**
- [ ] 飞书开放平台申请自建应用
- [ ] 记录 App ID、App Secret
- [ ] 申请权限：机器人、消息通知、卡片发送、通讯录只读、多维表格读写
- [ ] 找 IT 管理员批准权限

**开发工具**
- [ ] 本地安装 Docker Desktop
- [ ] 安装 pgAdmin 4 或 DBeaver
- [ ] 创建 GitHub 私有仓库
- [ ] 配置 OpenAI Codex + GPT 会员
- [ ] 本地安装 Python 3.11

**开始写 6 份知识资产文档**
- [ ] **schema.md** - 本周起步，第 1 周开发需要
- [ ] **workflows.md** - 本周起步，列出 10 个 workflow 的名字和简要描述
- [ ] **aliases.xlsx** - 组织业务员开 1 小时会整理
- [ ] **audit-rules.md** - 第 10 周前完成
- [ ] **queries.md** - 第 8 周前完成
- [ ] **business-defaults.md** - 第 7 周前完成

### 验收
- [ ] 能 SSH 登录两台云服务器
- [ ] 飞书机器人在测试群发 hello 成功
- [ ] GitHub 仓库有初始 README.md + AGENTS.md
- [ ] schema.md 完成核心 3 张表（合同、工单、委托）

---

## 第 1 周：项目骨架 + 数据库

### 目标
搭项目骨架，创建所有表，导入历史数据。

### Codex 任务 1.1：项目初始化

```
请创建 Python 项目 erp-ai-agent:

## 目录结构
erp-ai-agent/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI 入口
│   ├── config.py         # 配置（pydantic-settings）
│   ├── db/
│   │   ├── session.py
│   │   └── models/
│   ├── api/
│   ├── services/
│   ├── workflows/
│   ├── rules/
│   ├── audit/
│   ├── tools/
│   ├── agent/
│   ├── gateway/
│   └── utils/
├── tests/
├── alembic/
├── scripts/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── AGENTS.md
├── README.md
└── .env.example

## 依赖
fastapi, uvicorn, sqlalchemy[asyncio], alembic, asyncpg, psycopg2-binary,
pydantic, pydantic-settings, apscheduler, pytest, pytest-asyncio, pytest-cov,
ruff, black, mypy, httpx, python-dotenv

## Docker
docker-compose.yml 启动 PostgreSQL 16 + FastAPI 服务
PG 启用 pg_trgm 扩展

## 验收
1. docker-compose up -d 成功
2. http://localhost:8000/health 返回 {"status": "ok"}
3. pytest 能运行
4. README 说明启动步骤

请一步步实现，每个文件写清楚注释。
```

### Codex 任务 1.2：数据库 Schema

```
参考附件 schema.md，用 Alembic 创建表的迁移脚本:

1. 业务表: companies, brands, products, users, contracts,
   delivery_orders, delivery_delegations, transactions
2. 主数据表: company_aliases, brand_aliases, product_aliases,
   user_permissions, approval_rules, audit_rule_configs
3. 审计表: audit_logs, change_proposals, approval_records
4. History 表: contracts_history, delivery_orders_history,
   delivery_delegations_history, transactions_history
5. AI 运行表: conversations, messages, pending_issues
6. 辅助表: leave_records, role_holders

要求:
1. 所有表有通用字段: id (uuid), created_at, updated_at, version,
   created_by, updated_by
2. uuid 用 gen_random_uuid() 默认值
3. 外键明确声明
4. 重要字段加索引
5. History 表与业务表字段一致 + op_type, before_snapshot,
   after_snapshot, changed_fields, audit_log_id
6. 同时写对应的 SQLAlchemy 2.0 ORM 模型
7. 审计/history 表在 SQL 层设权限: INSERT + SELECT only

测试 tests/test_db_schema.py:
- 能建表
- 能插入 contract 数据
- 能 update 且 version 自增
- 能查 history 表
- 尝试 UPDATE audit_logs 应抛错

验收: alembic upgrade head 成功，pytest 全通过
```

### Codex 任务 1.3：历史数据导入（可选）

如果数据量小你自己导。量大让 Codex 写：

```
写 scripts/import_from_feishu.py:
- 输入: 飞书多维表格 App Token + Table ID
- 输出: 数据导入到 PG

要求:
1. 支持增量和全量
2. 数据类型转换（飞书日期 → PG date）
3. 日志写 logs/import.log
4. 失败行写 logs/import_failed.csv
5. 支持 --dry-run
```

### 你的验收
- [ ] pgAdmin 连上，所有表可见
- [ ] 手动插入一条 contract，update 一次，查 contracts_history 有两条
- [ ] 尝试 UPDATE audit_logs 被拒绝
- [ ] pytest 全通过
- [ ] git tag v0.1-week1

---

## 第 2 周：模糊匹配 + 查询工具基础

### 目标
实现模糊匹配 + 第一批基础查询工具。

### 前置
- [ ] aliases.xlsx 完成（≥50 公司 + 全部品牌 + 主要型号）

### Codex 任务 2.1：模糊匹配

```
实现模糊匹配，覆盖公司/品牌/型号三类。

数据准备:
scripts/import_aliases.py 从 aliases.xlsx 导入

核心服务 app/services/fuzzy_match.py:

async def fuzzy_match(
    entity_type: Literal["company", "brand", "product"],
    query: str,
    user_id: Optional[str] = None,
    max_results: int = 5,
) -> list[MatchCandidate]

匹配策略:
1. alias 精确匹配 → confidence 1.0（user_specific 优先于全局）
2. 正式名包含 query → 0.9
3. query 包含正式名 → 0.85
4. pg_trgm similarity > 0.3 → similarity 值

MatchCandidate: { id, name, match_type, confidence, matched_alias? }

API:
POST /api/fuzzy_match
  req: { entity_type, query, user_id? }
  resp: { candidates: [...], query: "美远" }

测试 tests/test_fuzzy_match.py:
- 精确 alias
- 名称包含
- 错别字（trigram）
- 多候选
- 零候选
- user_specific 生效/不生效
```

### Codex 任务 2.2：基础查询工具

```
在 app/tools/queries/ 下实现，每个函数用 @tool 装饰器。

工具:
1. search_contracts(contract_type?, customer_id?, brand_id?, product_id?,
   owner_user_id?, status?, signed_from?, signed_to?, valid_from?, valid_to?,
   _current_user_id) -> list[ContractRecord]

2. get_contract_detail(contract_id, _current_user_id) -> ContractDetail
   合同 + 关联提货工单 + 委托 + 已提货总量

3. search_deliveries(filters..., _current_user_id) -> list[DeliveryRecord]

4. search_transactions(filters..., _current_user_id) -> list[TransactionRecord]

5. search_pending_quantity(contract_type?, customer_id?, brand_id?,
   product_id?, owner_user_id?, only_active?, _current_user_id) -> list

权限:
- 每工具检查 _current_user_id 存在
- 查 user_permissions 决定数据范围
- admin 无过滤，其他用户按 owner_user_id 过滤

@tool 装饰器:
- 自动生成 JSON Schema
- 自动注入 _current_user_id
- 自动记录 tool_call_logs
- 自动参数类型转换

测试:
每工具至少 3 个测试（正常/权限/参数校验）
```

### 你的验收
- [ ] curl 调 /api/fuzzy_match 测真实简称
- [ ] 调 search_contracts 性能 < 200ms
- [ ] search_pending_quantity 结果和飞书多维表格核对一致
- [ ] pytest 全通过
- [ ] git tag v0.2-week2

---

## 第 3 周：Workflow 引擎核心

### 目标
实现 Workflow 引擎 + 第一个完整 workflow（update_contract_quantity）。

### Codex 任务 3.1：Workflow 框架

```
实现 Workflow 引擎框架。

数据结构 app/workflows/schema.py (Pydantic):

class ChangeOperation(BaseModel):
    op_type: Literal["insert", "update", "delete"]
    table: str
    record_id: Optional[str]
    before: Optional[dict]
    after: Optional[dict]

class ValidationViolation(BaseModel):
    rule_name: str
    severity: Literal["error", "warning"]
    message: str
    affected_records: list[dict] = []

class RequiredApprover(BaseModel):
    role: str
    sequence: int
    condition: Optional[str]

class Plan(BaseModel):
    id, workflow_name, workflow_version, params, operations,
    violations, required_approvers, status (PlanStatus enum),
    created_by, conversation_id, created_at

BaseWorkflow (app/workflows/base.py):

class BaseWorkflow(ABC):
    name, version, description, required_params, applicable_rules

    @abstractmethod
    async def plan(self, params, user_id, db) -> Plan

    async def validate_params(params)
    async def check_permission(user_id, params, db)
    async def save_plan(plan, db) -> str

规则引擎 (app/rules/):

class BaseRule(ABC):
    name, applies_to_tables

    @abstractmethod
    async def validate(self, plan, db) -> list[ValidationViolation]

class RuleEngine:
    def register(rule)
    async def run_rules(plan, rule_names, db) -> list[ValidationViolation]

测试 tests/test_workflow_framework.py 覆盖框架基础
```

### Codex 任务 3.2：首个 Workflow

```
实现 update_contract_quantity workflow。

文件 app/workflows/update_contract_quantity.py:

class UpdateContractQuantityWorkflow(BaseWorkflow):
    name = "update_contract_quantity"
    version = "1.0"
    required_params = ["contract_id", "new_quantity", "reason"]
    applicable_rules = [
        "delivery_not_exceed_contract",
        "quantity_positive",
        "status_allows_modification",
    ]

    async def plan(self, params, user_id, db):
        1. 校验参数
        2. 查合同（不存在抛 WorkflowError）
        3. 权限检查
        4. 生成 ChangeOperation
        5. 创建 Plan
        6. 跑 applicable_rules
        7. 无 error violation 则 status=pending_confirm
        8. 保存 Plan

规则实现:
- DeliveryNotExceedContract: new_quantity < 已提货 → error
- QuantityPositive: new_quantity > 0
- StatusAllowsModification: 只有 active 合同可改

CLI 测试 scripts/test_workflow.py:
用法: python scripts/test_workflow.py update_contract_quantity '{...}'
输出: Plan 的 JSON

必过测试:
1. 无提货合同 → 无 violation，pending_confirm
2. 已提 100 吨改为 50 吨 → error violation
3. 已提 100 吨改为 200 吨 → 无 violation
4. 不存在合同 → WorkflowError
5. completed 合同 → violation
6. new_quantity=0 → violation
7. 无权限用户 → PermissionError
```

### 你的验收
- [ ] pgAdmin 造 5 个合同（不同 status + 已提货量）
- [ ] CLI 跑 7 个用例全正确
- [ ] change_proposals 表有 Plan 记录
- [ ] audit_logs 还是空的（还没 execute）
- [ ] git tag v0.3-week3

---

## 第 4 周：Plan 执行 + 事务 + 审计

### 目标
Plan 真正落库，全程可回滚可审计。

### Codex 任务

```
实现 ProposalExecutor。

文件 app/services/executor.py:

class ProposalExecutor:
    async def execute(self, plan_id, user_id, db) -> AuditLog:
        async with db.begin():
            # 1. 加锁读 plan
            plan = await db.get(ChangeProposal, plan_id, with_for_update=True)
            if plan.status not in [PENDING_CONFIRM, APPROVED]:
                raise ExecutorError
            
            # 2. status → EXECUTING
            plan.status = PlanStatus.EXECUTING
            
            # 3. 重跑规则
            workflow = workflow_registry.get(plan.workflow_name)
            violations = await rule_engine.run_rules(
                plan, workflow.applicable_rules, db
            )
            errors = [v for v in violations if v.severity == "error"]
            if errors:
                plan.status = PlanStatus.FAILED
                raise ValidationFailed(errors)
            
            # 4. 创建 audit_log
            audit_log = AuditLog(
                id=uuid4(),
                plan_id=plan.id,
                conversation_id=plan.conversation_id,
                workflow_name=plan.workflow_name,
                user_id=user_id,
                operations=plan.operations,
                status="in_progress",
                executed_at=now(),
            )
            db.add(audit_log)
            await db.flush()
            
            # 5. 执行 operations
            for op in plan.operations:
                await self._execute_operation(op, audit_log.id, user_id, db)
            
            # 6. 事后核验
            await workflow.verify_post_execution(plan, db)
            
            # 7. 状态收尾
            audit_log.status = "success"
            plan.status = PlanStatus.COMPLETED
            plan.audit_log_id = audit_log.id
            
            return audit_log

    async def _execute_operation(self, op, audit_log_id, user_id, db):
        model = get_model_by_table(op.table)
        
        if op.op_type == "insert":
            record = model(**op.after)
            db.add(record)
            await db.flush()
            await self._write_history(...)
        
        elif op.op_type == "update":
            record = await db.get(model, op.record_id, with_for_update=True)
            if not record: raise ExecutorError
            # 乐观锁校验
            if op.before.get("version") and record.version != op.before["version"]:
                raise ExecutorError("数据已被修改，请重新生成 Plan")
            
            before_snapshot = to_dict(record)
            for k, v in op.after.items():
                setattr(record, k, v)
            record.version += 1
            record.updated_by = user_id
            
            await self._write_history(...)
        
        elif op.op_type == "delete":
            record = await db.get(model, op.record_id, with_for_update=True)
            before_snapshot = to_dict(record)
            await db.delete(record)
            await self._write_history(...)

测试:
1. 正常 update → 成功，数据变，history 有，audit_log 有
2. 规则二次校验失败 → 回滚
3. 事后核验失败 → 回滚
4. 并发 update 同一合同 → 乐观锁只一个成功
5. 已 completed plan 再次执行 → 拒绝
6. 执行中抛异常 → 回滚

API:
POST /api/plans/{plan_id}/execute
```

### 你的验收
- [ ] 完整流程：CLI 生成 Plan → API 执行 → 4 张表都正确
- [ ] 故意让核验失败，确认回滚
- [ ] 并发测试
- [ ] git tag v0.4-week4

---

## 第 5 周：接入 LLM + 会话 + CLI 对话

### 目标
用 Hermes 调 OpenAI，跑通完整对话（CLI 交互）。

### 前置
- [ ] business-defaults.md 完成
- [ ] queries.md 至少 20 个示例

### Codex 任务 5.1：LLM 调用 + 会话管理

```
实现对话管理和 LLM 调用。

Hermes 集成 app/agent/llm_client.py:
- 启动时以 subprocess 方式起 Hermes（或用其 Python API，看最新文档）
- 传 OpenAI 配置
- 封装 LLMClient.chat(messages, tools, tool_choice) → ChatResponse

会话管理 app/agent/conversation_manager.py:

class ConversationManager:
    async def get_or_create_session(user_id) -> Conversation
        # 30 分钟无活动自动新建
    
    async def append_message(conversation_id, role, content, ...)
    
    async def get_context_messages(conversation_id, max_tokens=8000) -> list[dict]
        # 超长: 最近 10 轮 + 之前压缩为 summary
    
    async def end_session(conversation_id)
    async def reset_session(user_id)  # /new 命令

Agent 核心 app/agent/orchestrator.py:

class AgentOrchestrator:
    async def handle_message(user_id, user_message) -> AssistantResponse:
        1. get_or_create_session
        2. append user message
        3. 拼 context (system prompt + summary + recent messages)
        4. LLM 调用循环（最多 10 轮 tool use）:
           - 若有 tool_calls: 依次执行（自动注入 _current_user_id）
           - 若无: 最终回答，append assistant message，return
        5. 超过迭代 raise AgentError
    
    async def _execute_tool(name, args, user_id, session_id):
        args["_current_user_id"] = user_id
        args["_conversation_id"] = session_id
        # 记录 tool_call 消息
        # 调工具
        # 记录 tool_result 消息
        return result

System prompt app/agent/prompts.py:
参考项目蓝本第 7 节骨架，补充:
- 从 business-defaults.md 读默认值
- 从用户权限读用户能力
- Few-shot 示例（几个典型对话）

CLI scripts/chat_cli.py:
- 交互式 REPL
- 打印 AI 回答
- /new /quit /debug 命令

测试:
- 30 分钟会话重置
- Context 压缩
- tool 调用时 _current_user_id 强制注入
```

### Codex 任务 5.2：MCP 工具注册

```
把查询和 workflow 工具注册到 Agent。

工具清单:
- fuzzy_match_company / brand / product
- search_contracts
- get_contract_detail
- search_pending_quantity
- propose_update_contract_quantity
- confirm_proposal
- cancel_proposal

每工具 JSON Schema:
- 清晰 description（LLM 看这个决定何时用）
- 参数说明
- 不暴露 _current_user_id 给 LLM

System prompt 更新:
- 加入工具描述
- Few-shot 示例:

示例 1（查询，单候选）:
User: 美远还剩多少没提？
Assistant 内部:
  tool: fuzzy_match_company("美远") → [{id:"C001", name:"美远贸易"}]
  (单候选，按默认 confidence 1.0 使用)
  tool: query_customer_pending_summary(customer_id="C001", contract_type="sales")
  → [...]
Assistant: 按销售合同查询（如需采购请补充）:
  美远贸易还剩 195 吨未提:
  - C20260312 三房 302, 签约 330, 已提 135, 剩余 195, 至 2026-06-30
  ...

示例 2（查询，多候选）:
User: 美远还剩多少没提？
Assistant 内部:
  tool: fuzzy_match_company("美远") → [C001 美远贸易, C015 美远国际]
Assistant: 你是指哪个美远？
  1. 美远贸易
  2. 美远国际

示例 3（写操作）:
User: 把 C20260312 改成 200 吨
Assistant 内部:
  tool: propose_update_contract_quantity(contract_id="C20260312", new_quantity=200)
  → Plan(violations=[], status=pending_confirm)
Assistant: 我将要执行:
  - 合同 C20260312 数量 330 → 200
  - 理由是？

(用户补充理由后)
User: 客户要求
Assistant 内部:
  tool: propose_update_contract_quantity(..., reason="客户要求")
  → Plan(id="P001")
Assistant: 准备执行 Plan P001:
  ... 详情 ...
  确认吗？ (yes/no)
User: yes
Assistant 内部:
  tool: confirm_proposal(plan_id="P001")
Assistant: ✓ 已执行
```

### 你的验收
- [ ] CLI 跑通对话（参考示例 3 的流程）
- [ ] messages 表有完整记录
- [ ] conversations 表 30 分钟无活动后新对话开新 session
- [ ] 故意传错 user_id 到工具，验证被强制覆盖
- [ ] git tag v0.5-week5

---

## 第 6 周：飞书 Gateway

### 目标
把 CLI 的一切搬到飞书。

### Codex 任务

```
实现飞书 Gateway 服务。

文件 app/gateway/feishu/:
- client.py: 飞书 SDK 封装
- event_handler.py: 事件订阅回调
- card_renderer.py: Plan → 飞书卡片 JSON
- card_callback.py: 卡片按钮点击回调
- user_mapper.py: open_id → user_id 映射

事件订阅:
- 订阅 im.message.receive_v1（接收机器人消息）
- 订阅 card.action.trigger（卡片按钮点击）
- webhook 签名验证
- 事件 ID 去重（幂等）

处理流程:
收到消息:
  1. 验证签名
  2. 查 open_id → user_id（不存在则拒绝）
  3. 调 AgentOrchestrator.handle_message(user_id, text)
  4. 把返回的 AssistantResponse 渲染:
     - 普通文本 → 发文本消息
     - Plan 预览 → 发交互卡片

卡片渲染 (Plan 预览):
{
  "header": { "title": "操作预览 - {workflow_name}" },
  "elements": [
    { "tag": "div", "text": "摘要..." },
    { "tag": "div", "text": "详情..." },
    { "tag": "hr" },
    ("⚠️ 需要审批: X" if required_approvers),
    { "tag": "action", "actions": [
      { "tag": "button", "text": "确认执行", "type": "primary",
        "value": { "action": "confirm", "plan_id": "..." }},
      { "tag": "button", "text": "取消", "type": "default",
        "value": { "action": "cancel", "plan_id": "..." }}
    ]}
  ]
}

卡片回调:
收到 card.action.trigger:
  1. 验证签名
  2. 解析 value
  3. 如果 action=confirm: 调 confirm_proposal
  4. 如果 action=cancel: 调 cancel_proposal
  5. 更新卡片显示结果

长对话处理:
飞书消息接口 3 秒超时 → 长任务异步处理:
  1. 立即回 ACK
  2. 后台异步 handle_message
  3. 完成后主动推消息

测试:
用飞书的事件测试工具模拟发送事件
```

### 你的验收
- [ ] 飞书里私信机器人：「把 C001 改成 200 吨」
- [ ] AI 回复卡片
- [ ] 点确认，数据库变，AI 回复"已执行"
- [ ] 点取消，Plan 状态变 cancelled
- [ ] 连续两条消息，AI 记得上下文
- [ ] 30 分钟后发消息，开新会话
- [ ] git tag v0.6-week6

---

## 第 7 周：审批流

### 目标
让 Plan 执行前走审批，支持请假转移。

### 前置
- [ ] workflows.md 第 10 个 workflow 的审批要求都想清楚了

### Codex 任务

```
实现审批流引擎。

## 数据准备
- approval_rules 表导入初始规则（YAML 格式可读文件）
- role_holders 表录入各角色的当前主责人
- leave_records 表结构 + UI 不做（手动 SQL 录入先）

## 核心服务 app/services/approval/

### RuleMatcher
class ApprovalRuleMatcher:
    async def match(plan: Plan, db) -> list[RequiredApprover]
        # 按 priority 排序的 rules 遍历
        # 匹配 workflow_name + match_condition（支持简单表达式）
        # 返回按 sequence 的审批人角色列表

### ApproverResolver  
async def resolve_approver(role, context, date, db) -> user_id:
    # 1. 查 role_holders 当前主责人
    # 2. 查 leave_records 看是否请假
    # 3. 请假则查委托人
    # 4. 委托人也请假则上级
    # 5. 全不在则返回默认兜底

### ApprovalOrchestrator
class ApprovalOrchestrator:
    async def initiate(plan_id, db):
        # Plan.required_approvers 转为实际 user_id
        # 为 sequence=1 的审批人创建 approval_record(status=pending)
        # 发送飞书审批卡片
    
    async def handle_decision(record_id, decision, comment, user_id):
        # 更新 approval_record
        # 如果 approved: 看是否还有下一级 sequence
        #   有: 发给下一级
        #   无: 调 ProposalExecutor.execute
        # 如果 rejected: plan.status = REJECTED
        # 如果 delegated: 转移给指定人
    
    async def check_timeout():
        # APScheduler 定时任务
        # pending 超过 2 小时未决: 发提醒
        # 超过 4 小时: 自动升级到上级

## 飞书审批卡片
与预览卡片不同：
- 展示 Plan 概要
- 按钮: 同意 / 拒绝 / 转交
- 点"转交"弹出选人对话（用飞书 @人 功能或自定义）

## Webhook 端点
POST /webhooks/feishu/card_action
- 处理审批决定
- 处理 Plan 确认/取消（第 6 周已有）

## 测试
1. 小额修改无需审批 → 直接执行
2. 大额修改需要 2 级审批 → 卡片下发，同意后执行
3. 第 1 级拒绝 → Plan 变 rejected
4. 审批人请假 → 自动路由到委托人
5. 超过 2 小时无响应 → 提醒
```

### 你的验收
- [ ] 配一条"修改合同需部门主管审批"的规则
- [ ] 发起修改，卡片发到主管飞书
- [ ] 主管点同意，执行成功
- [ ] 主管点拒绝，Plan 状态 rejected
- [ ] 模拟主管请假（SQL 改 leave_records），验证转移到委托人
- [ ] git tag v0.7-week7

---

## 第 8 周：补齐 Workflow + 权限

### 目标
实现剩余 workflow + 权限系统。

### 前置
- [ ] workflows.md 全部 10 个 workflow 细节完成

### Codex 任务 8.1：剩余 workflow（本周 5 个）

```
实现以下 workflows（每个一套：workflow 类 + 所需规则 + 测试）:

1. create_sales_contract - 新建销售合同
2. create_purchase_contract - 新建采购合同
3. update_contract_price - 修改合同单价
4. cancel_contract - 作废合同
5. create_delivery_order - 新建提货工单

（按 workflows.md 详细规格实现）

参考第 3 周的模板。每个 workflow 至少 5 个测试用例。
```

### Codex 任务 8.2：权限系统

```
实现用户权限系统。

数据: user_permissions 表

规则:
{
  user_id: "U001",
  workflow_name: "update_contract_quantity",
  scope_filter: {"owner_user_id": "$user_id"},  # 只能操作自己负责的
  allowed: true
}

实现:

### PermissionChecker (app/services/permission.py)

class PermissionChecker:
    async def can_execute_workflow(user_id, workflow_name, params, db) -> bool
    async def can_view_record(user_id, table, record_id, db) -> bool
    async def filter_visible_records(user_id, table, query) -> filtered_query

### 应用点
1. 每个 workflow 的 check_permission 调 can_execute_workflow
2. 每个查询工具底层调 filter_visible_records
3. get_contract_detail 调 can_view_record

### 默认权限规则
- admin: 全部允许
- sales: 能查所有合同，但只能改 owner=self 的
- 单证: 能查所有，能 CRUD 提货工单/委托
- 财务: 能录流水，能查所有，拆合同需审批

测试:
- 越权场景：张三改李四的合同 → 被拒
- 权限过滤：张三查合同只看到自己的
```

### 你的验收
- [ ] 5 个新 workflow 都能在飞书里用自然语言触发
- [ ] 张三尝试改李四的合同被拒
- [ ] 张三查合同列表只看到自己的
- [ ] git tag v0.8-week8

---

## 第 9 周：补齐 Workflow + 第二层查询工具

### 目标
剩余 5 个 workflow + 业务语义查询工具。

### Codex 任务 9.1：剩余 workflow

```
实现:
6. create_delivery_delegation
7. update_delivery_quantity
8. split_executed_contract (最复杂那个，拆合同)
9. record_transaction
10. [你的 workflows.md 里列的第 10 个]

split_executed_contract 特别注意:
- 涉及多表、多记录
- 前置检查严格（已执行、提货链可拆分）
- 遇到拆分不整除要暂停问用户
- 事后核验：拆分前后总量守恒
```

### Codex 任务 9.2：第二层查询工具

```
实现业务语义查询工具。

工具:

1. query_customer_pending_summary(
     customer_id, contract_type="sales",
     include_completed=False, _current_user_id
   ) -> CustomerPendingSummary
   
   返回:
   {
     customer: {id, name},
     total_signed, total_delivered, total_remaining,
     by_brand: [{brand, signed, delivered, remaining, contracts: [...]}],
     by_contract: [{contract_number, brand, product, quantity, ...}]
   }

2. query_brand_pending_summary(brand_id, ...) -> BrandSummary

3. query_monthly_statistics(
     month="2026-04",
     contract_type="sales",
     group_by="customer" | "brand" | "owner",
     _current_user_id
   ) -> MonthlyStats

4. query_user_performance(
     user_id, period, _current_user_id
   ) -> UserPerformance

### 幻觉防护：结构化输出 + 后置校验

AI 输出格式变为:
{
  "summary": "文字总结",
  "evidence": [
    { "contract_number": "...", "field1": val1, ... },
    ...
  ],
  "data_source": "query_customer_pending_summary",
  "query_params": {...}
}

后置校验器 app/agent/response_verifier.py:
class ResponseVerifier:
    def verify(ai_response, tool_results):
        for evidence in ai_response.evidence:
            found = find_in_tool_results(tool_results, ...)
            if not found: raise HallucinationDetected
            for field in check_fields:
                if evidence[field] != found[field]:
                    raise HallucinationDetected

失败处理: 不返回 AI 回答，返回 "系统检测到数据一致性问题，请重试"，
记录告警日志。
```

### 你的验收
- [ ] 拆合同 workflow 跑完整的一次（可用测试数据）
- [ ] 飞书问"美远还剩多少没提"，回答准确含证据
- [ ] 故意 mock AI 返回一个不存在的合同号，验证后置校验抛错
- [ ] git tag v0.9-week9

---

## 第 10 周：审计引擎 + 待办系统

### 目标
实现审计规则引擎 + 待办自愈 + 飞书多维表格同步。

### 前置
- [ ] audit-rules.md 完成

### Codex 任务

```
实现审计引擎。

## AuditRule 基类 (app/audit/base.py)

class AuditRule(ABC):
    name: str
    category: str
    severity: str
    
    @abstractmethod
    async def check(self, db) -> list[Violation]
    
    @abstractmethod
    async def determine_owner(self, violation, db) -> list[str]  # user_ids
    
    def generate_issue_key(self, violation) -> str
    def get_title(self, violation) -> str

## 规则注册 + 调度 (app/audit/engine.py)

class AuditEngine:
    def __init__(self, db_factory):
        self.rules: dict[str, AuditRule] = {}
    
    def register(self, rule: AuditRule)
    
    async def run_rule(self, rule_name: str):
        rule = self.rules[rule_name]
        async with db_factory() as db:
            async with db.begin():
                current_detected_keys = set()
                violations = await rule.check(db)
                
                for v in violations:
                    key = rule.generate_issue_key(v)
                    current_detected_keys.add(key)
                    
                    existing = await db.query(PendingIssue)\
                        .filter_by(issue_key=key, status='open').first()
                    
                    if existing:
                        existing.last_seen_at = now
                        existing.detection_count += 1
                    else:
                        owner_user_ids = await rule.determine_owner(v, db)
                        db.add(PendingIssue(
                            rule_name=rule.name,
                            issue_key=key,
                            category=rule.category,
                            severity=rule.severity,
                            title=rule.get_title(v),
                            description=v.description,
                            affected_records=v.records,
                            owner_user_ids=owner_user_ids,
                            status='open',
                            first_detected_at=now,
                            last_seen_at=now,
                            detection_count=1,
                        ))
                
                # 自愈
                stale = await db.query(PendingIssue)\
                    .filter_by(rule_name=rule.name, status='open')\
                    .filter(PendingIssue.issue_key.notin_(current_detected_keys))\
                    .all()
                
                for issue in stale:
                    issue.status = 'resolved'
                    issue.resolved_at = now
                    issue.resolution_method = 'auto_resolved'
        
        # 触发飞书同步（异步）
        asyncio.create_task(sync_pending_issues_to_feishu())

## 调度器 (app/audit/scheduler.py)

使用 APScheduler + audit_rule_configs 表:

on_startup:
    configs = await db.query(AuditRuleConfig).filter_by(enabled=True).all()
    for cfg in configs:
        scheduler.add_job(
            audit_engine.run_rule,
            CronTrigger.from_crontab(cfg.cron_expression),
            args=[cfg.rule_name],
            id=cfg.rule_name,
        )

## 实现初始规则集（8 条，参考 audit-rules.md）

1. bare_delivery_order_check (每小时)
2. bare_delivery_delegation_check (每小时)
3. daily_sales_purchase_balance (每天 3:00)
4. daily_transaction_contract_balance (每天 3:00)
5. orphan_records_check (每 6 小时)
6. approval_compliance_check (每天)
7. contract_quantity_conservation (每小时)
8. date_timeline_consistency (每天)

## 飞书多维表格同步 (app/audit/feishu_sync.py)

class PendingIssuesFeishuSync:
    async def sync():
        # 全量或增量同步到飞书多维表格
        # 每 5 分钟运行（APScheduler）
        # open 状态的同步到看板
        # resolved 的从看板移除（或移到"已解决"视图）

## MCP 工具 (app/tools/audit/)

- get_my_pending_issues(_current_user_id) -> list
- explain_issue(issue_id, _current_user_id) -> str
- mark_issue_manual_override(issue_id, reason, _current_user_id)  # 管理员

## 测试

1. 造裸工单 → 等 1 小时跑审计 → pending_issues 有记录
2. 补上对应委托 → 下次审计 → 自动 resolved
3. owner_user_ids 正确
4. 用户 A 查看自己的待办 → 只看到自己的
5. 飞书同步每 5 分钟运行一次
```

### 你的验收
- [ ] 手动造一个裸工单，等 1 小时后 pending_issues 有记录
- [ ] 补上委托，等下次审计自动 resolved
- [ ] 飞书多维表格"待办看板"能看到记录
- [ ] 飞书问 AI "我有哪些待办"，返回只属于自己的
- [ ] git tag v0.10-week10

---

## 第 11 周：灰度测试 + AI 日报

### 目标
小范围灰度 + 收集 bad case + AI 日报功能。

### Codex 任务 11.1：AI 日报

```
实现每日审计日报。

文件 app/audit/daily_report.py:

class DailyReporter:
    async def generate(date, for_user_id) -> DailyReport:
        # 收集昨日数据:
        - 业务概况：新增合同数、提货数、总吨数
        - 硬规则结果：每条规则通过/异常
        - pending_issues 变化：新增、解决、累积
        - AI 使用情况：对话数、成功率、主要 workflow
        
        # 调 LLM 用 template 生成自然语言报告
        # 返回结构化 + 自然语言版
    
    async def send_to_user(user_id, report):
        # 飞书卡片推送（简版）
        # PDF 存档（详版）

调度:
每天 8:00 生成并推给老板 + 财务

模板 templates/daily_report.j2:
【{date} 业务审计日报】

## 业务概况
- 新增合同: 销售 {} 笔，采购 {} 笔
- 提货: 工单 {} 笔，委托 {} 笔
- 总提货量: {} 吨

## 硬规则结果
{for rule in rules}
{rule.icon} {rule.name}: {rule.result}
{endfor}

## 待办进度
- 新增: {}
- 已解决: {}
- 累积: {}

## AI 运营
- 对话数: {}
- 成功率: {}%
- 主要 workflow:
{for wf in top_workflows}
  - {wf.name}: {wf.count}
{endfor}

## 需要关注
{for issue in attention_items}
- {issue.title}
{endfor}
```

### 你的灰度工作

**选择灰度用户**
- [ ] 选 2-3 个最信任的业务员 + 财务
- [ ] 在飞书群里做一次半小时的培训（演示 + 他们自己试用）

**跟踪 bad case**
开始记录 bad_cases.md：
```
## Case #1 (2026-MM-DD)
用户: 张三
对话: "把美远的单子拆成两半"
AI 理解: [具体怎么理解的]
问题: AI 没有先问是哪个美远客户
修复: 在 prompt 里加强调"公司名有多候选必须问"
修复结果: ✓
```

**每天复盘**
- 前 7 天每天晚上跟灰度用户聊 5 分钟，问"今天 AI 有没有搞错什么"
- 所有 case 记录下来
- 当晚让 Codex 修（配合 Claude 审查）

### 你的验收
- [ ] 日报功能正常推送
- [ ] bad_cases.md 至少记录 10 个 case 并全部解决
- [ ] 灰度用户主观反馈"好用"
- [ ] git tag v0.11-week11

---

## 第 12 周：硬化 + 全员上线

### 目标
压力测试 + 灾备演练 + 全员培训 + 上线。

### Codex 任务 12.1：硬化

```
做以下加固工作:

1. 限流与并发控制
   - 每用户每分钟最多 20 条消息
   - 每 workflow 同时只能有 1 个 pending plan 针对同一记录
   - 全局 LLM 调用速率限制

2. 错误恢复
   - LLM 返回 JSON 解析失败 → 友好提示重新表述
   - 工具超时 → 重试 1 次，失败则友好报错
   - 数据库连接失败 → 优雅降级

3. 监控
   - APScheduler 任务健康监控
   - 飞书 API 调用成功率监控
   - LLM 调用延迟监控
   - 失败率超过阈值发告警（飞书通知你）

4. 日志规范
   - 所有关键操作日志都有 trace_id
   - 错误日志带完整上下文
   - 生产环境日志写文件 + 定期归档

5. 数据备份
   - PG 每日 pg_dump 到对象存储
   - 保留 30 天
   - 每周全量 + 每日增量
   - 定期恢复测试

6. 备机同步
   - 主机 PG 每小时 rsync 到备机
   - 写 scripts/failover.sh 一键切换
   - DNS TTL 设为 60 秒方便切换
```

### 你的任务：上线准备

**灾备演练**
- [ ] 停主机，切备机，验证业务恢复（模拟故障）
- [ ] 从备份恢复一次 PG，验证数据完整

**全员培训**
- [ ] 写一份《业务员使用手册》（1 页纸）：
  - 如何在飞书找到机器人
  - 常用查询示例
  - 如何查看待办
  - 遇到错误怎么反馈
- [ ] 组织 1 小时全员培训会

**上线策略（软着陆）**
- [ ] 前 1 周：AI 系统和老系统（飞书多维表格）并行运行
- [ ] 第 2 周：鼓励使用 AI，保留老系统紧急用
- [ ] 第 3 周：关闭老系统写权限（只读看板）
- [ ] 第 4 周：完全切换

**沟通渠道**
- [ ] 建一个"AI 反馈"飞书群，所有用户入群
- [ ] 任何 bug 或建议都在群里说
- [ ] 你每天看 + 响应

### 你的验收
- [ ] 灾备演练通过
- [ ] 全员培训完成
- [ ] 第一周无重大 bug
- [ ] git tag v1.0-launch

---

## 12 周后的运营

### 持续工作（每周）

1. **抽检 AI 行为**（1 小时）
   - 随机抽 20 条 AI 操作的完整链路
   - 特别关注被用户取消的、执行后被撤销的
   - 发现问题更新 prompt 或规则

2. **审计 alias 表**（10 分钟）
   - 过去一周累积的待晋升 alias
   - 手动确认 / 驳回
   - 加入全局 alias 表

3. **查看待办解决率**（10 分钟）
   - 超过 7 天未解决的 pending_issues 单独列出
   - 找负责人沟通原因

### Phase 2 开发优先级（3 个月稳定后评估）

1. 利润分析（最有商业价值）
2. 库存预警
3. 跨会话长期记忆优化
4. 软性异常检测

---

## 风险预警：这些坑你可能遇到

1. **第 3-4 周时发现 schema 设计有问题**
   - 表结构改动要小心，有 history 表要同步改
   - 尽早发现，别等第 8 周才返工
   - 预防：第 1 周 schema.md 多花时间，找懂业务的同事 review

2. **第 5-6 周接入 LLM 时发现效果不理想**
   - AI 意图识别准确率低、工具选错
   - 通常不是模型问题，是 prompt 或工具描述问题
   - 解决：把错误对话发给 Claude 让它分析 prompt 怎么改

3. **第 8-9 周发现某些 workflow 业务逻辑很复杂**
   - 特别是 split_executed_contract
   - 预留 buffer 时间，不要死磕时间线
   - 宁可简化第一版，保留管理员手动兜底

4. **第 10 周审计规则误报率高**
   - 业务上有些"异常"是正常的
   - 解决：细化规则的边界条件；增加 "exclusion list"

5. **第 11 周灰度时业务员抗拒**
   - 老系统用惯了，新系统不熟
   - 解决：老板推动 + AI 真的好用 + 并行期足够长

6. **第 12 周压力测试发现性能问题**
   - 某些查询慢（特别是 search_pending_quantity 跨多表 join）
   - 解决：加索引、改写查询、或引入缓存

---

## 文档结束

这份计划是一个相对详细的路线图，但不是死的：
- 每周末回顾一次，调整下周任务
- 遇到新需求先评估值不值得插入本期
- 不值得的记下来放 Phase 2

**12 周后的你**，应该有一个：
- 10 个业务员日常使用的 AI 助手
- 所有操作可审计、可回溯
- 业务异常自动发现并追踪
- 查询问答准确快速
- 管理者（你）每天能看到有价值的日报

**祝你开发顺利。有任何问题随时打开新对话，把这两份文档贴进去，Claude 能无缝续接。**

---

*v1.0 - 2026-04-19*
