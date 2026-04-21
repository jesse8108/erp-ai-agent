# 会话延续文档

> **目的**: 本文档让你（项目发起人）在开启新对话时，把这份文档贴给新的 Claude，能立刻理解项目的全貌、当前进度、设计决策、接下来的任务。
>
> **使用方式**:
> 1. 新开 Claude 对话
> 2. 把以下 5 份文档都上传或贴给 Claude：
>    - 本文件（00-continuation-guide.md）
>    - 01-project-blueprint.md（项目蓝本）
>    - 02-development-plan.md（12 周开发计划）
>    - schema.md v0.6（数据库设计）
>    - workflows.md v0.1（工作流定义）
> 3. 告诉新 Claude："先读完这些文档再回答我的问题"
> 4. 开始提你的新问题

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

## 六、当前项目阶段

### 已完成文档（✅）

1. ✅ **01-project-blueprint.md**：项目蓝本（架构、设计哲学、子系统设计）
2. ✅ **02-development-plan.md**：12 周开发计划（每周 codex 任务模板）
3. ✅ **schema.md v0.6**：数据库 schema（2258 行，所有表 + 视图 + TRIGGER）
4. ✅ **workflows.md v0.1**：10 个核心 workflow 定义（876 行）
5. ✅ **00-continuation-guide.md**：本文档

### 待完成文档（⏳）

1. ⏳ **aliases.xlsx**：公司/品牌/型号简称表（需组织业务员 1 小时会议整理）
2. ⏳ **audit-rules.md**：审计规则清单（第 10 周前完成）
3. ⏳ **queries.md**：日常查询场景清单（第 8 周前完成）
4. ⏳ **business-defaults.md**：业务默认值规则（第 7 周前完成）

### 开发阶段（当前：第 -1 周，准备期）

**第 0 周（准备工作，未开始）**:
- [ ] 购买云服务器（主机 + 备机 4C8G Ubuntu 22.04）
- [ ] 申请飞书自建应用，获取 App ID / App Secret
- [ ] 创建 GitHub 私有仓库
- [ ] 配置 OpenAI Codex + GPT 会员
- [ ] 整理 aliases.xlsx（50 个客户 + 全品牌 + 主要型号）
- [ ] 确定 6 个业务员的飞书 open_id

**第 1 周（项目骨架 + 数据库，未开始）**:
- 任务 1.1: Python 项目初始化（FastAPI + Docker）
- 任务 1.2: 数据库 Schema（按 schema.md v0.6 建 30 张表 + 5 个视图）
- 任务 1.3: 历史数据导入

**第 2 周到第 12 周**：按开发计划文档推进

---

## 七、关键对话历史与重要决策记录

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

## 八、下一步任务优先级

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

## 九、新对话中可能的问题类型

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

## 十、常见误区提醒（给新 Claude）

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

## 十一、联系信息（发起人自填）

```
云服务器主机: [待购买]
云服务器备机: [待购买]
飞书应用 App ID: [待申请]
飞书应用 App Secret: [待申请]
GitHub 仓库: [待创建]
OpenAI Codex 账号: [已配置 / 待配置]
```

---

## 十二、给新 Claude 的初始指令建议

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
| 00-continuation-guide.md | v2.0 | ~400 | ✅ 本文档 |
| 01-project-blueprint.md | v1.0 | ~1100 | ✅ 稳定 |
| 02-development-plan.md | v1.0 | ~1400 | ✅ 稳定 |
| schema.md | v0.6 | ~2260 | ✅ 封顶 |
| workflows.md | v0.1 | ~880 | ✅ 首版，开发时迭代 |

---

*v2.0 - 2026-04-20 完整项目状态快照*
*通过这份文档，你随时可以从任何一次对话断点，无缝接回项目。*
