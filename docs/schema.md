# schema.md - 业务表结构定义

> **版本**: v0.9 (brand_aliases / product_aliases 完整设计 + AI 简称查询逻辑)
> **状态**: 所有表定稿 ✅ 可直接交付 Codex 第 1 周建库
> **数据分析样本**: 250 合同 + 64 工单 + 58 委托 + 37 调度 + 713 流水 + 1712 客户档案 + 34 品牌 + 45 型号 + 55 提货地 + 46 品牌简称 + 77 型号简称

---

## 关于此文档

本文档定义 ERP 系统所有业务表的字段级规格。开发时 Codex 根据此文档创建数据库表、ORM 模型、迁移脚本。

**设计原则**:
- 字段类型用 PostgreSQL 类型
- enum 值完整列出
- 业务规则写具体，可翻译为代码约束
- 跨字段约束单独列出
- 所有聚合字段（已提货量、敞口库存、应收付等）**都是运行时计算，不存储**
- 历史数据的脏数据模式专门标注，供导入时清洗
- **所有业务数据一律软删除，严禁物理删除**
- **合同的数量和单价是真源，不可被下游工单/委托修改**
- **流水表只读不可改，对账通过视图实现（汇总级对账，不做流水-合同关联）**

**v0.9 改动**（简称表完整设计）:
- **第 8 节完整改写**：从"（略）"占位变为 brand_aliases / product_aliases 完整设计（约 130 行）
- **brand_aliases 表**：字段定义 + UNIQUE 约束 + 46 条初始数据来源（`data-import/brand_aliases_final.xlsx`）
- **product_aliases 表**：字段定义 + 关键设计 `brand_id` 冗余存储 + UNIQUE 约束 + 77 条初始数据来源
- **新增 8.6 节**：AI 处理简称查询的标准 3 步流程（精确匹配 → 上下文过滤 → fuzzy fallback / 反问）
- **新增 8.7 节**：简称冲突检测 SQL（运维定期跑）
- **歧义处理统一为方案乙**：所有歧义简称（数字编码型 + 品类词型）都进表标 `is_ambiguous=true`，AI 看到歧义统一反问品牌

**v0.8 改动**（基于真实 PostgreSQL 主数据重构）:
- **重构 `delivery_locations` 表**：从全局共享变为**品牌专属**，加 `brand_id` 外键 + 地理字段（`lng`/`lat`/`adcode`/`citycode`）+ `sort_order`
- **`brands` 表种子数据扩到 34 个品牌**（之前 5.1 节只列了 12 个历史合同里出现的品牌）
- **`products` 表种子数据 45 个型号**（每个型号挂在具体品牌下；"大有光"、"水料"、"油料"作为通用品类型号在多个品牌下重复存在，业务上合理）
- **删除 `delivery_locations.name UNIQUE 约束`**：同一地名（如"江阴"）可在多个品牌下各存一条
- **新增章节 7.5**：业务员说"江阴提"的 AI 处理逻辑（必须在已知品牌上下文内）
- **新增附录 B**：品牌/型号/提货地的导入流程（用 brand_name 关联 → 运行时生成 uuid）
- **新增附录 C**：历史合同导入时的品牌名映射（旧名 → 新标准名）

**v0.7 改动**:
- `companies` 表扩展工商信息字段（法人、注册资本、注册地、经营范围、开户行等）
- `companies` 表新增 `external_code`（历史档案编号）、`legal_person`、`registered_address` 等字段
- `company_aliases` 表 `source` 枚举新增 `auto_generated` 值
- `company_aliases` 表新增 `generator_version` 字段（记录生成算法版本，便于批量重算）
- `company_aliases` 表加入软删除字段（业务员可删除误生成的简称）
- 新增"公司工商信息获取 API"的集成说明
- 新增"简称自动生成规则"的完整描述（见附录 A）

**v0.6 改动**:
- 流水表（transactions）完整定稿：只读、不关联合同、3 重保护
- 新增 4 个对账视图（规范化流水、按对方汇总流水、按对方汇总合同、最终对账视图）
- 补充 audit_logs / change_proposals / approval_records 完整 DDL
- 补充 history 表通用规范（5 张业务表 history）
- 补充 AI 运行表完整 DDL（conversations / messages / pending_issues / tool_call_logs）
- 补充配置表（user_permissions / approval_rules / audit_rule_configs / role_holders / leave_records）

**v0.5 改动**:
- 价格模型锁定（合同单价是真源）
- 调度拆分规则（提货地/品牌/型号任一不同就拆分）

**v0.4 改动**:
- `margin_deduction_mode` 字段
- 视图加入 receivable_amount / payable_amount
- 提货工单/委托/调度完整定义

**v0.3 改动**:
- 全局软删除机制

**v0.2 改动**:
- 基于 250 条历史合同数据定稿，7 种合同类型

---

## 0. 公司主体结构（重要背景）

本公司业务涉及三家关联公司，schema 设计必须理解它们各自的角色：

| 公司名 | 代号 | 角色 |
|-------|------|------|
| 安徽趋易贸易有限公司 | subject_a | **我方主体**，直接参与销售/采购合同 |
| 上海瞿谊实业有限公司 | subject_b | **我方主体**，直接参与销售/采购合同 |
| 上海骋子次方商务服务有限公司 | (不入数据) | 撮合主体，只做中介，**不作为合同甲乙方出现** |

**关键约束**:
- 主体 A 和主体 B 之间**不会有内部交易**（业务已确认）
- 撮合主体 C 不作为合同数据中的一方
- 每份**销售类**合同的甲方必然是 subject_a 或 subject_b
- 每份**采购类**合同的乙方必然是 subject_a 或 subject_b
- **撮合合同**的甲方和乙方都是外部公司（我方不是交易主体）

---

## 0.5 软删除机制（全局规则）

### 0.5.1 核心原则

**任何业务表（contracts, delivery_orders, delivery_delegations, transactions 等）严禁物理删除 (DELETE FROM ...)**。所有"删除"操作都是软删除：在记录上填写 `deleted_at` 时间戳。

### 0.5.2 区分两个不同层面的概念

理解这一点至关重要：**"作废"和"删除"是两件不同的事**，混为一谈会造成严重的设计混乱。

| 场景 | 本质 | 使用字段 | 查询时 |
|------|------|---------|--------|
| 合同业务上终止（客户违约、双方协商终止、货源缺失） | **业务行为** | `contract_status = 'cancelled'` | 正常显示，标注"已作废" |
| 合同录错了/重复录入/测试数据 | **数据行为** | `deleted_at` 有时间戳 | 默认过滤，不显示 |

**状态组合示意**：

| 含义 | contract_status | deleted_at |
|------|----------------|-----------|
| 正常执行中 | `in_progress` | NULL |
| 正常完结 | `completed` | NULL |
| **业务作废**（保留历史） | `cancelled` | NULL |
| **逻辑删除**（录错等） | 任何状态 | 有时间戳 |
| 作废后又发现是误录 | `cancelled` | 有时间戳 |

### 0.5.3 所有业务表的通用软删除字段

所有业务表（合同、提货工单、提货委托、流水）都必须包含以下字段：

| 字段名 | 类型 | 必填 | 含义 |
|-------|------|------|------|
| deleted_at | timestamptz | N | 软删除时间；NULL 表示未删除 |
| deleted_by | uuid | N | 执行软删除的用户（FK → users） |
| deleted_reason | text | N | 删除原因（软删除时必填） |

**约束**: `deleted_at IS NOT NULL` 时 `deleted_by` 和 `deleted_reason` 必填；`deleted_at IS NULL` 时这三个字段都应为 NULL。

### 0.5.4 主数据表的不同处理

**主数据表**（users, companies, brands, products, delivery_locations）不用 `deleted_at` 机制，改用 `is_active` 字段：

| 表 | 字段 | 说明 |
|----|------|------|
| users | `is_active`, `left_at` | 离职员工 is_active=false，历史合同依然显示姓名 |
| companies | `is_active` | 注销的公司标记，历史合同正常引用 |
| brands | `is_active` | 停产品牌标记 |
| products | `is_active` | 停产型号标记 |
| delivery_locations | `is_active` | 停用仓库标记 |

**新建合同时的校验**: 不允许选择 `is_active = false` 的主数据，但**已存在的合同引用不受影响**。

### 0.5.5 UNIQUE 约束的特殊处理

所有原本 UNIQUE 的字段（如 `contract_number`, `feishu_open_id`）改为**部分唯一索引**，只对未删除记录生效：

```sql
-- 错误写法（会导致软删除后无法用同样的编号新建）
CREATE UNIQUE INDEX idx_contracts_number ON contracts(contract_number);

-- 正确写法（部分唯一索引）
CREATE UNIQUE INDEX idx_contracts_number_active
  ON contracts(contract_number) WHERE deleted_at IS NULL;
```

这样允许合同号在**软删除的错录合同**和**新合同**之间复用。

### 0.5.6 外键的处理

**软删除不使用 CASCADE**。合同被软删除时：
- 关联的提货工单/委托**不自动删除**
- 外键引用依然指向这条"已删除"的合同
- 查询关联数据时能明确看到"指向已删除记录"的情况
- 这是**有意设计**——便于审计和恢复

**配套的审计规则**: 新增 `orphan_delivery_to_deleted_contract_check` 审计规则——提货工单指向已软删除的合同时，标记为严重异常。

### 0.5.7 查询的默认过滤

在 SQLAlchemy ORM 基类上配置默认过滤，所有查询自动加 `deleted_at IS NULL`：

```python
# app/db/models/base.py
class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

# 查询时默认过滤已删除
class Contract(Base, SoftDeleteMixin):
    ...

# 默认 query (过滤已删除)
session.query(Contract).all()  # 自动加 WHERE deleted_at IS NULL

# 管理员查询（含已删除）
session.query(Contract).execution_options(include_deleted=True).all()
```

**关键要求**: AI 调用的所有查询工具**必须使用默认过滤**，只有管理员后台才能查看已删除记录。

### 0.5.8 软删除与 history 表

软删除本身也是一次 UPDATE 操作，必须写入 history 表：

```
history 记录:
  op_type: 'soft_delete'
  before_snapshot: { ...合同完整数据, deleted_at: NULL }
  after_snapshot: { ...合同完整数据, deleted_at: '2026-04-20 10:30:00', deleted_by: 'xxx', deleted_reason: '重复录入' }
  changed_fields: ['deleted_at', 'deleted_by', 'deleted_reason', 'version', 'updated_at', 'updated_by']
  audit_log_id: 关联到 AI 对话触发的 audit_log
```

即使合同被删除了，完整的"曾经长什么样"依然在 history 里。

### 0.5.9 删除相关的三个 Workflow

在 workflows.md 里要设计三个独立 workflow：

**Workflow: `cancel_contract`（作废合同）** — 业务行为
- 操作：`contract_status` → `cancelled`
- 保留所有数据，正常查询能看到
- 必须填写作废原因
- 需审批
- 如有关联提货记录，提示业务员是否需要同步处理（不强制）

**Workflow: `soft_delete_contract`（逻辑删除合同）** — 数据行为
- 操作：`deleted_at` 填时间戳
- 适用场景：录错了/重复了/测试数据
- 必须填写删除原因
- 需更严格审批（比作废更严格）
- **前置检查**：如果有关联的非删除状态的提货记录，先提示业务员是否一并软删除，或要求先处理关联数据

**Workflow: `restore_deleted_contract`（恢复误删）** — 管理员能力
- 操作：`deleted_at` 置回 NULL
- 只有老板或管理员能执行
- 必须填写恢复原因
- 自动检查：如果当前存在与被恢复合同的 `contract_number` 相同的活跃合同，拒绝恢复

### 0.5.10 AI 对话中的意图区分

AI 的 system prompt 必须明确区分"作废"和"删除"：

```
用户说"删除合同" → 默认理解为"作废"（业务行为），调 cancel_contract
用户说"这个录错了删掉" / "这是重复的" → 调 soft_delete_contract
用户说"恢复刚才误删的 XX" → 调 restore_deleted_contract（只有管理员）

如果用户表述模糊，必须反问:
"你是想要：
A) 作废这份合同（业务上不执行了，但保留记录以便对账）
B) 删除这条录入（因为录错了或重复了）"
```

这条规则要写进 business-defaults.md。

### 0.5.11 审计与对账的特殊考虑

软删除引入了新的审计维度：

- **误删监测**：短时间内（如 24 小时）软删除又恢复的情况要标记，防止滥用
- **孤儿检测**：提货工单指向已软删除合同 → 严重异常
- **级联检测**：软删除合同后，如果关联提货未处理，生成待办

这些规则在 audit-rules.md 里专门列出。

---

## 1. contracts（合同表）

### 1.1 用途

记录销售、采购、撮合、借货四大类业务合同，是 ERP 核心主表。

**记录量级**: 每月约 60-100 条，当前累计约 250 条

### 1.2 合同类型（核心分类）

系统区分 **4 大类 7 小类**合同：

| 大类 | 小类（enum 值） | 含义 | 我方角色 | 我方主体参与 |
|------|---------------|------|---------|-------------|
| 销售 | `sales` | 我方直销，主体 A 或 B 作为甲方卖给外部客户 | 卖方 | ✅ 甲方 |
| 采购 | `purchase` | 我方直采，主体 A 或 B 作为乙方从外部供应商买入 | 买方 | ✅ 乙方 |
| 撮合 | `brokering` | 纯撮合，甲乙方都是外部公司，我方赚佣金 | 中介 | ❌ |
| 撮合 | `brokering_sales` | 撮合下的销售侧，主体 A 或 B 为甲方，有撮合业务员参与 | 卖方 | ✅ 甲方 |
| 撮合 | `brokering_purchase` | 撮合下的采购侧，主体 A 或 B 为乙方，有撮合业务员参与 | 买方 | ✅ 乙方 |
| 借货 | `lending_sales` | 借货给外部方（主体 A/B 为甲方借出），对方付保证金，还货后退保证金 | 借出方 | ✅ 甲方 |
| 借货 | `lending_purchase` | 从外部方借货（主体 A/B 为乙方借入），付保证金，还货后退保证金 | 借入方 | ✅ 乙方 |

**销售 vs 撮合销售的区别**:
- 销售: 纯我方业务员跟进，无撮合佣金拆分
- 撮合销售: 撮合业务员介绍来的生意，要按佣金规则分成

**借货合同的业务逻辑**:
- 数据结构上和销售/采购完全一样（走同样的字段和 workflow）
- 差别在业务语义：`total_amount` 是账面价值非实际付款，`margin_amount` 是抵押金非预付款
- 合同完结的语义是"对方归还了货物并退还了保证金"

### 1.3 字段定义

#### 1.3.1 标识字段

| 字段名 | 类型 | 必填 | 含义 | 约束 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | PK, default gen_random_uuid() |
| contract_number | varchar(50) | Y | 合同编号 | UNIQUE |

**合同编号格式**: 样本中 76 种前缀格式（`CZCH-`, `HY-`, `QYXS-` 等），**系统只保证 UNIQUE，不做格式校验**。

#### 1.3.2 分类与状态字段

| 字段名 | 类型 | 必填 | 含义 | 约束 |
|--------|------|------|------|------|
| contract_type | enum | Y | 合同类型 | 见 1.2 |
| contract_status | enum | Y | 合同状态 | `not_started` / `in_progress` / `completed` / `cancelled` |

**contract_status 枚举**:
- `not_started`（未执行）: 40 条样本
- `in_progress`（执行中）: 10 条样本
- `completed`（已完结）: 200 条样本
- `cancelled`（已作废）: 新系统新增，历史数据中无此状态

**状态流转规则**:
```
not_started → in_progress：首次有提货发生时自动流转
in_progress → completed：提货总量达到 quantity_tons 时自动流转
                        （借货合同为"对方还货完成"）
not_started / in_progress → cancelled：需审批，不可逆转
completed → cancelled：不允许直接转换，必须走 split_contract 等特殊 workflow
```

#### 1.3.3 主体与交易对手字段（核心重构）

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| our_subject_company | enum | 条件必填 | 我方主体，`subject_a` / `subject_b` / NULL |
| our_role | enum | Y | 我方角色，`seller` / `buyer` / `broker_only` / `lender` / `borrower` |
| party_a_name | varchar(200) | Y | 甲方名称（法律合同中的称呼） |
| party_a_company_id | uuid | N | 甲方外部公司 ID（软关联，FK → companies） |
| party_b_name | varchar(200) | Y | 乙方名称 |
| party_b_company_id | uuid | N | 乙方外部公司 ID（软关联） |

**our_subject_company 条件必填规则**:
```
IF contract_type = 'brokering':
    our_subject_company 必须为 NULL（撮合合同我方不是主体）

IF contract_type != 'brokering':
    our_subject_company 必填（subject_a 或 subject_b 二选一）
```

**our_role 自动推导规则**（不用业务员填，从 contract_type 推导）:
```
sales, brokering_sales → seller
purchase, brokering_purchase → buyer
brokering → broker_only
lending_sales → lender
lending_purchase → borrower
```

**甲乙方与 our_subject_company 的一致性约束**:
```
IF contract_type IN ('sales', 'brokering_sales', 'lending_sales'):
    party_a_name 必须等于 our_subject_company 对应的公司全名

IF contract_type IN ('purchase', 'brokering_purchase', 'lending_purchase'):
    party_b_name 必须等于 our_subject_company 对应的公司全名

IF contract_type = 'brokering':
    party_a_name 和 party_b_name 都**不得**等于任何我方主体公司全名
```

**party_*_company_id 的软关联策略**:
- Phase 1: 合同保留甲方/乙方的**文本名称**为主，company_id 可空
- 不强制要求所有合同的对方公司都在 companies 表中注册
- 好处：导入历史数据时不会因为"对方公司名对不上主数据"而失败
- Phase 2: 逐步规范化，最终目标是所有合同都有 company_id

#### 1.3.4 业务员归属字段

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| salesperson_user_id | uuid | 条件必填 | 主责业务员（FK → users） |
| broker_party_a_user_id | uuid | 条件必填 | 撮合甲方业务员（FK → users） |
| broker_party_b_user_id | uuid | 条件必填 | 撮合乙方业务员（FK → users） |

**条件必填规则**:
```
IF contract_type IN ('sales', 'purchase'):
    salesperson_user_id 必填
    broker_party_a_user_id 和 broker_party_b_user_id 必须为 NULL

IF contract_type IN ('brokering', 'brokering_sales', 'brokering_purchase'):
    broker_party_a_user_id 必填
    broker_party_b_user_id 必填
    salesperson_user_id 可为 NULL（允许一笔撮合业务同时有主业务员跟进）

IF contract_type IN ('lending_sales', 'lending_purchase'):
    salesperson_user_id 必填（借货也是销售/采购业务）
    broker 字段可为 NULL（除非借货是通过撮合达成）
```

**历史数据**: 66 条记录（撮合类 + 部分借货类）的 salesperson_user_id 为空。导入时：
- 撮合类为空合法
- 借货类为空需标记待补充（上线后逐步完善）

#### 1.3.5 商品字段

| 字段名 | 类型 | 必填 | 含义 | 约束 |
|--------|------|------|------|------|
| brand_id | uuid | Y | 品牌 | FK → brands |
| product_model | varchar(100) | N | 型号 | 4 条历史数据为空（水料），允许空 |
| quantity_tons | decimal(12,3) | Y | 数量（吨） | > 0 |
| unit_price | decimal(10,2) | N | 单价（元/吨） | > 0 when not null |
| delivery_location_id | uuid | Y | 提货地 | FK → delivery_locations |

**unit_price 可空说明**: 少数借货或特殊合同可无单价。

#### 1.3.6 时间字段

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| signed_date | date | Y | 签订日期 |
| valid_from | date | Y | 合同开始时间 |
| valid_to | date | Y | 合同结束时间 |

**业务规则**:
- `valid_to > valid_from` （强约束）
- `signed_date ≤ valid_from` （软规则，不强制——偶有补签情况）

#### 1.3.7 保证金字段

| 字段名 | 类型 | 必填 | 含义 | 约束 |
|--------|------|------|------|------|
| margin_type | enum | N | 保证金方式 | `full` / `fixed_ratio` / `fixed_amount` |
| fixed_ratio | decimal(5,4) | 条件必填 | 固定比例（0 < x ≤ 1） | |
| fixed_amount | decimal(12,2) | 条件必填 | 固定金额（元） | > 0 |
| margin_deduction_mode | enum | 条件必填 | 保证金扣除模式 | `proportional` / `at_end` |

**margin_type 枚举**:
- `full`（全款）: 108 条，保证金 = 合同总金额
- `fixed_ratio`（固定比例）: 131 条，保证金 = 总金额 × 固定比例
- `fixed_amount`（固定金额）: 7 条，保证金 = fixed_amount

**margin_deduction_mode 枚举**（仅 fixed_ratio / fixed_amount 场景适用）:
- `proportional`（按比例扣除）: 每次提货的应收/付 = 已提量 × 单价 × (1 - 保证金率) + 保证金金额。即每车只收"货款的 1-保证金率"部分，保证金挂账一直存在
- `at_end`（最后扣除）: 前期每车按全价付货款，剩余可提量 ≤ 保证金对应吨数时，应收/付锁定为合同总金额

**注意**: 原历史数据中的 `margin_amount` 字段**不存储**，改为运行时计算（见 1.4）。

**条件必填规则**:
```
IF margin_type = 'full':
    fixed_ratio 必须为 NULL
    fixed_amount 必须为 NULL
    margin_deduction_mode 必须为 NULL（全款不需要扣除模式）

IF margin_type = 'fixed_ratio':
    fixed_ratio 必填
    fixed_amount 必须为 NULL
    margin_deduction_mode 必填（proportional 或 at_end）

IF margin_type = 'fixed_amount':
    fixed_amount 必填
    fixed_ratio 必须为 NULL
    margin_deduction_mode 必填（proportional 或 at_end）

IF margin_type IS NULL:
    fixed_ratio, fixed_amount, margin_deduction_mode 都必须为 NULL
```

**历史数据脏数据**: 34 条 margin_type=full 的记录同时填了 fixed_ratio（冗余）。导入时清洗，把这些 fixed_ratio 置空。历史数据需补充 `margin_deduction_mode`（可通过业务员批量核实，或给所有 fixed_ratio 的历史记录暂时填 `proportional` 作为默认值后人工复核）。

**借货合同的保证金语义**:
- `margin_type` 仍按上述三种取值
- 但业务上叫"抵押金"而不是"预付款"
- 合同完结时保证金需退回（由流水记录反映）
- 借货合同的应收/付计算逻辑特殊（见 1.4）

#### 1.3.8 交付方式字段

| 字段名 | 类型 | 必填 | 含义 | 约束 |
|--------|------|------|------|------|
| delivery_method | enum | N | 交付方式 | `self_pickup` / `shipped` |
| freight_per_ton_incl_tax | decimal(8,2) | N | 含税运费（元/吨） | ≥ 0 |
| find_truck_freight_excl_tax | decimal(10,2) | N | 帮找车运费（元/车，不含税） | ≥ 0 |

**delivery_method 枚举**:
- `self_pickup`（自提）: 208 条，买方自提
- `shipped`（送到）: 38 条，我方负责送到

**软约束**（不强制）:
- `self_pickup` 下 `freight_per_ton_incl_tax` 通常为空，`find_truck_freight_excl_tax` 偶尔有值（帮买方安排运输）
- `shipped` 下 `freight_per_ton_incl_tax` 通常有值

#### 1.3.9 合同总金额

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| total_amount | decimal(14,2) | Y | 合同总金额 |

**计算规则**:
```
IF unit_price IS NOT NULL:
    total_amount = quantity_tons × unit_price
    （应用约束: 允许 0.01 元以内的四舍五入误差）
IF unit_price IS NULL:
    total_amount 允许人工录入
```

历史数据 100% 符合此规则 ✅

**不再存储的字段**（都改为运行时计算）:
- `receivable_payable_amount`（历史字段，新系统提货事件级计算）
- `margin_amount`
- `delivered_tons_sales` / `delivered_tons_purchase`（从 delivery_orders / delegations 聚合）
- `open_stock_sales` / `open_stock_purchase`
- `total_commission_party_a` / `total_commission_party_b`

#### 1.3.10 撮合佣金字段（仅撮合类合同）

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| commission_per_ton_party_a | decimal(8,2) | 条件必填 | 甲方佣金单价（元/吨） |
| commission_per_ton_party_b | decimal(8,2) | 条件必填 | 乙方佣金单价（元/吨） |

**条件必填规则**:
```
IF contract_type LIKE 'brokering%':
    commission_per_ton_party_a 必填（可为 0）
    commission_per_ton_party_b 必填（可为 0）
ELSE:
    两字段必须为 NULL
```

**总佣金**: 运行时计算（见 1.4），非存储字段。

#### 1.3.11 其他字段

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| notes | text | N | 备注 |
| attachments | jsonb | N | 附件列表（Phase 2 实现） |

#### 1.3.12 通用审计字段（所有表共有）

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| created_by | uuid | Y | 创建人（FK → users） |
| created_at | timestamptz | Y | 创建时间 |
| updated_by | uuid | Y | 最后更新人（FK → users） |
| updated_at | timestamptz | Y | 最后更新时间 |
| version | int | Y | 乐观锁版本号，默认 1 |

#### 1.3.13 软删除字段（所有业务表共有）

见 0.5 章完整说明。字段定义：

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| deleted_at | timestamptz | N | 软删除时间；NULL 表示未删除 |
| deleted_by | uuid | N | 执行软删除的用户（FK → users） |
| deleted_reason | text | N | 删除原因 |

**约束**:
- `deleted_at IS NOT NULL` 时 `deleted_by` 和 `deleted_reason` 必填
- `deleted_at IS NULL` 时这三个字段都应为 NULL

**这三个字段的组合约束**通过数据库 CHECK 约束强制（见 1.5 完整 DDL）。

### 1.4 运行时计算字段（通过 VIEW 暴露）

以下字段**不在 contracts 表中存储**，通过 SQL VIEW 或应用层实时计算，彻底避免数据不一致问题。

#### 视图: `v_contracts_with_aggregates`

**注意**：此视图默认**只包含未软删除的合同**（`deleted_at IS NULL`）。另建一个 `v_contracts_with_aggregates_including_deleted` 视图供管理员查看。

```sql
CREATE VIEW v_contracts_with_aggregates AS
WITH base AS (
  SELECT
    c.*,
    -- 保证金金额
    CASE c.margin_type
      WHEN 'full' THEN c.total_amount
      WHEN 'fixed_ratio' THEN c.total_amount * c.fixed_ratio
      WHEN 'fixed_amount' THEN c.fixed_amount
      ELSE NULL
    END AS margin_amount,
    
    -- 已提货量（销售侧）
    COALESCE((
      SELECT SUM(do.quantity_tons) FROM delivery_orders do
      WHERE do.sales_contract_id = c.id 
        AND do.status != 'cancelled'
        AND do.deleted_at IS NULL
    ), 0) AS delivered_tons_sales,
    
    -- 已提货量（采购侧）
    COALESCE((
      SELECT SUM(dd.quantity_tons) FROM delivery_delegations dd
      WHERE dd.purchase_contract_id = c.id 
        AND dd.status != 'cancelled'
        AND dd.deleted_at IS NULL
    ), 0) AS delivered_tons_purchase,
    
    -- 销售侧额外费用汇总（所有关联工单的 extra_fee 之和）
    COALESCE((
      SELECT SUM(do.extra_fee) FROM delivery_orders do
      WHERE do.sales_contract_id = c.id 
        AND do.status != 'cancelled'
        AND do.deleted_at IS NULL
    ), 0) AS total_extra_fee_sales,
    
    -- 采购侧额外费用汇总
    COALESCE((
      SELECT SUM(dd.extra_payment) FROM delivery_delegations dd
      WHERE dd.purchase_contract_id = c.id 
        AND dd.status != 'cancelled'
        AND dd.deleted_at IS NULL
    ), 0) AS total_extra_payment_purchase
  FROM contracts c
  WHERE c.deleted_at IS NULL
)
SELECT
  base.*,
  
  -- 敞口库存
  base.quantity_tons - base.delivered_tons_sales AS open_stock_sales,
  base.quantity_tons - base.delivered_tons_purchase AS open_stock_purchase,
  
  -- 销售应收款（仅对 our_role=seller/broker_only 的合同有意义）
  CASE 
    -- 撮合纯中介：不计算应收应付
    WHEN base.contract_type = 'brokering' THEN NULL
    -- 借货合同：只有保证金
    WHEN base.contract_type LIKE 'lending_%' THEN 
      COALESCE(base.margin_amount, 0) + base.total_extra_fee_sales
    -- 非销售侧合同：此字段无意义
    WHEN base.our_role NOT IN ('seller', 'lender') THEN NULL
    -- 全款
    WHEN base.margin_type = 'full' THEN 
      base.total_amount + base.total_extra_fee_sales
    -- 按比例扣除
    WHEN base.margin_deduction_mode = 'proportional' THEN 
      base.delivered_tons_sales * base.unit_price 
      * (1 - base.margin_amount / NULLIF(base.total_amount, 0))
      + base.margin_amount 
      + base.total_extra_fee_sales
    -- 最后扣除
    WHEN base.margin_deduction_mode = 'at_end' THEN
      CASE 
        WHEN (base.quantity_tons - base.margin_amount / NULLIF(base.unit_price, 0)) 
             > base.delivered_tons_sales THEN
          base.delivered_tons_sales * base.unit_price + base.margin_amount + base.total_extra_fee_sales
        ELSE
          base.total_amount + base.total_extra_fee_sales
      END
    ELSE NULL
  END AS receivable_amount,
  
  -- 采购应付款（仅对 our_role=buyer/borrower 的合同有意义）
  CASE 
    WHEN base.contract_type = 'brokering' THEN NULL
    WHEN base.contract_type LIKE 'lending_%' THEN 
      COALESCE(base.margin_amount, 0) + base.total_extra_payment_purchase
    WHEN base.our_role NOT IN ('buyer', 'borrower') THEN NULL
    WHEN base.margin_type = 'full' THEN 
      base.total_amount + base.total_extra_payment_purchase
    WHEN base.margin_deduction_mode = 'proportional' THEN 
      base.delivered_tons_purchase * base.unit_price 
      * (1 - base.margin_amount / NULLIF(base.total_amount, 0))
      + base.margin_amount 
      + base.total_extra_payment_purchase
    WHEN base.margin_deduction_mode = 'at_end' THEN
      CASE 
        WHEN (base.quantity_tons - base.margin_amount / NULLIF(base.unit_price, 0)) 
             > base.delivered_tons_purchase THEN
          base.delivered_tons_purchase * base.unit_price + base.margin_amount + base.total_extra_payment_purchase
        ELSE
          base.total_amount + base.total_extra_payment_purchase
      END
    ELSE NULL
  END AS payable_amount,
  
  -- 总撮合佣金（仅撮合类合同，基于实际提货量）
  CASE WHEN base.contract_type LIKE 'brokering%' THEN
    COALESCE(base.commission_per_ton_party_a, 0) * base.delivered_tons_sales
  ELSE NULL END AS total_commission_party_a,
  
  CASE WHEN base.contract_type LIKE 'brokering%' THEN
    COALESCE(base.commission_per_ton_party_b, 0) * base.delivered_tons_purchase
  ELSE NULL END AS total_commission_party_b

FROM base;
```

**公式业务说明**（给 Codex 验证用）：

用合同：100 吨 × 8000 元/吨 × 保证金 10% = 合同总金额 80 万、保证金 8 万
- 全款：应收恒为 80 万 + 额外费用
- 按比例扣除 + 已提 33 吨：`33 × 8000 × 0.9 + 80000 = 317,600` + 额外费用
- 最后扣除 + 已提 33 吨：`33 × 8000 + 80000 = 344,000` + 额外费用（此时剩余 67 吨 > 10 吨保证金对应量，按全额）
- 最后扣除 + 已提 92 吨：`= 800,000` + 额外费用（此时剩余 8 吨 ≤ 10 吨，锁定合同总金额）
- 借货 + 保证金 8 万：应收 = 80,000 + 额外费用

### 1.5 索引建议

```sql
CREATE INDEX idx_contracts_type ON contracts(contract_type);
CREATE INDEX idx_contracts_status ON contracts(contract_status);
CREATE INDEX idx_contracts_subject ON contracts(our_subject_company);
CREATE INDEX idx_contracts_salesperson ON contracts(salesperson_user_id);
CREATE INDEX idx_contracts_broker_a ON contracts(broker_party_a_user_id);
CREATE INDEX idx_contracts_broker_b ON contracts(broker_party_b_user_id);
CREATE INDEX idx_contracts_signed_date ON contracts(signed_date DESC);
CREATE INDEX idx_contracts_valid_range ON contracts(valid_from, valid_to);
CREATE INDEX idx_contracts_brand ON contracts(brand_id);
-- 模糊搜索
CREATE INDEX idx_contracts_party_a_trgm ON contracts USING gin(party_a_name gin_trgm_ops);
CREATE INDEX idx_contracts_party_b_trgm ON contracts USING gin(party_b_name gin_trgm_ops);
-- 组合索引（最常用的查询：查某业务员负责的活跃合同）
CREATE INDEX idx_contracts_salesperson_status ON contracts(salesperson_user_id, contract_status);
-- 软删除相关索引
CREATE INDEX idx_contracts_deleted_at ON contracts(deleted_at) WHERE deleted_at IS NOT NULL;
-- 部分唯一索引（只对未删除记录强制唯一）
CREATE UNIQUE INDEX idx_contracts_number_active 
  ON contracts(contract_number) WHERE deleted_at IS NULL;
```

**关键说明**：`contract_number` 的 UNIQUE 约束不在表定义里（`UNIQUE NOT NULL`），改为部分唯一索引。这样：
- 未删除合同之间 `contract_number` 必须唯一 ✅
- 软删除的合同不占用 `contract_number` 空间
- 新合同可以复用已软删除的合同号

### 1.6 历史数据导入清洗规则

导入 2026-04-20 导出的 250 条历史数据时需要的清洗动作：

| 清洗项 | 原数据 | 清洗后 |
|--------|-------|-------|
| 合同类型中文转 enum | "撮合采购" | `brokering_purchase` |
| 合同状态中文转 enum | "已完结" | `completed` |
| 保证金方式中文转 enum | "固定比例" | `fixed_ratio` |
| 交付方式中文转 enum | "自提" | `self_pickup` |
| 业务员姓名转 user_id | "李成子" | 对应 users.id |
| 识别 our_subject_company | 检查甲方/乙方名称是否包含"安徽趋易"或"上海瞿谊" | 填入 subject_a 或 subject_b |
| our_role 推导 | 根据 contract_type 自动计算 | seller/buyer/broker_only/lender/borrower |
| fixed_ratio 清洗 | margin_type=full 同时填了 fixed_ratio 的 34 条 | 把 fixed_ratio 置空 |
| 丢弃字段 | receivable_payable_amount, margin_amount, 已提货量, 敞口库存, 总佣金 | 不存入合同表（视图计算） |
| 附件字段 | 全为空 | 导入为 NULL |

### 1.7 关键约束检查清单（Codex 实现时必做）

在 workflow 的 validate 阶段实现以下跨字段约束（数据库 CHECK 约束 + 应用层二次校验）：

- [ ] `our_subject_company` 的条件必填（brokering 必空，其他必填）
- [ ] `salesperson` vs `broker` 字段的互斥关系（根据合同类型）
- [ ] `party_a_name` / `party_b_name` 与 `our_subject_company` 的一致性
- [ ] `margin_type` 和 `fixed_ratio`/`fixed_amount`/`margin_deduction_mode` 的四路互斥
- [ ] `margin_deduction_mode` 条件必填：full 时必空、fixed_* 时必填
- [ ] `commission_per_ton_*` 的条件必填（撮合类必填、其他必空）
- [ ] `total_amount = quantity_tons × unit_price`（允许 0.01 误差）
- [ ] `valid_to > valid_from`
- [ ] `quantity_tons > 0`
- [ ] `contract_status` 流转合法性
- [ ] **软删除三字段一致性**：`deleted_at IS NOT NULL` ⇔ `deleted_by IS NOT NULL` ⇔ `deleted_reason IS NOT NULL`
- [ ] **软删除后禁止再更新**：已软删除的记录除了"恢复操作"外不可修改
- [ ] **恢复前检查号码冲突**：恢复软删除的合同前校验 `contract_number` 是否与现有活跃合同冲突

---

## 2. users（内部员工表）

### 2.1 用途
记录公司内部员工，关联飞书身份，权限控制基础。

### 2.2 软删除策略

**注意**: users 表**不使用** `deleted_at` 机制，改用 `is_active` + `left_at`。离职员工不会从系统中消失，历史合同和操作记录依然引用他们的姓名。

### 2.3 字段定义

| 字段名 | 类型 | 必填 | 含义 | 说明 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | |
| feishu_open_id | varchar(100) | Y | 飞书 open_id | 见下说明 |
| name | varchar(50) | Y | 姓名 | |
| roles | text[] | Y | 角色列表（支持一人多角色） | 见下 |
| is_active | boolean | Y | 是否在职 | 默认 true |
| joined_at | date | N | 入职日期 | |
| left_at | date | N | 离职日期 | |

**feishu_open_id 的唯一约束**: 使用部分唯一索引，只对 `is_active = true` 的记录强制唯一

```sql
CREATE UNIQUE INDEX idx_users_feishu_active
  ON users(feishu_open_id) WHERE is_active = true;
```

**roles 枚举值**（一人可以有多个）:
- `sales` - 销售业务员
- `purchase` - 采购业务员
- `broker` - 撮合业务员
- `clerk` - 单证（做提货工单/委托）
- `finance` - 财务
- `admin` - 系统管理员
- `boss` - 老板（全局可见）

### 2.4 初始数据（基于合同数据聚合）

| 姓名 | 出现合同数 | 推测主角色 |
|-----|----------|----------|
| 李成子 | 82 | ['sales', 'broker'] |
| 祝晓彤 | 43 | ['sales'] |
| 黄佳欣 | 33 | ['broker', 'sales']（撮合较多）|
| 游鑫淼 | 17 | ['sales'] |
| 陈凯丽 | 9 | ['sales'] |
| 邢光 | 创建了全部 250 条 | ['admin', 'clerk']（系统管理员，代录入）|

**待你确认**: 每个人的具体 role（可多选）、飞书 open_id。

---

## 3. companies（交易对手公司表）

### 3.1 用途
记录外部交易对手公司（客户 + 供应商），支持模糊匹配。

**不包括我方主体公司**（subject_a / subject_b 硬编码在 enum，骋子次方不入数据）。

### 3.2 字段定义

#### 3.2.1 标识字段

| 字段名 | 类型 | 必填 | 含义 | 约束 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | PK, default gen_random_uuid() |
| formal_name | varchar(200) | Y | 正式全名 | 部分唯一索引（见 3.4）|
| external_code | varchar(50) | N | 原档案编号（从飞书档案继承，如 `22E3ND0F68555E2` 或 `C-260417-001`）| |
| tax_id | varchar(30) | N | 统一社会信用代码（18 位）| 见 3.3 |

#### 3.2.2 业务分类

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| company_type | enum | N | `customer`（客户）/ `supplier`（供应商）/ `both`（既买又卖）|
| business_relation_type | varchar(30) | N | 细分业务关系：`贸易商` / `下游工厂` / `一般客户` / `上游厂家` / `撮合对方` 等（保留原档案的细分标签）|

**company_type 与 business_relation_type 的关系**：
- `company_type` 是系统级分类，用于工具权限和查询过滤
- `business_relation_type` 是业务语义标签，保留原档案的细粒度信息，不参与权限判断
- 一般映射：贸易商 → `both`、下游工厂 → `customer`、上游厂家 → `supplier`、一般客户 → `customer`
- 映射规则可在导入时配置，也允许业务员人工调整

#### 3.2.3 工商信息字段（新增于 v0.7）

这些字段由**工商信息 API**（发起人后续接入）或人工录入填充。AI 不应要求业务员手动填这些字段，而是：
- 业务员只提供"公司名称"
- `create_company` workflow 调用工商 API 查询详情
- 查询成功 → 自动填充；查询失败 → 只保留 formal_name，其他字段留空

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| legal_person | varchar(50) | N | 法定代表人 |
| registered_capital | varchar(50) | N | 注册资本（保留原文，如 "500万人民币"）|
| paid_in_capital | varchar(50) | N | 实缴资本 |
| business_status | varchar(30) | N | 经营状态：`存续` / `在营` / `注销` / `吊销` / `停业` 等（原文保留）|
| enterprise_type | varchar(100) | N | 企业类型（如"有限责任公司（自然人独资）"）|
| registered_address | text | N | 注册地址（原文保留，可能是 JSON 结构或纯文本）|
| established_date | date | N | 成立日期 |
| business_expire_date | date | N | 营业有效期截止日期 |
| business_scope | text | N | 经营范围（原文，通常很长）|
| bank_name | varchar(200) | N | 开户行 |
| bank_account | varchar(50) | N | 银行账号 |

**说明**：
- 工商 API 返回的字段全部是可选的（API 可能查不到或信息不全）
- 这些字段 AI 通常不会主动展示给业务员，除非业务员问"XX 公司的详细信息"
- `business_scope` 字段内容通常很长（几百到几千字），查询时按需返回

#### 3.2.4 状态与审计字段

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| is_active | boolean | Y | 是否激活，默认 true；注销/吊销的公司历史合同依然引用但不允许新建 |
| notes | text | N | 备注（自由文本）|
| created_by | uuid | Y | 创建人（FK → users）|
| created_at | timestamptz | Y | 创建时间 |
| updated_by | uuid | Y | 最后更新人 |
| updated_at | timestamptz | Y | 最后更新时间 |
| version | int | Y | 乐观锁，默认 1 |

**说明**：
- `companies` 是**主数据表**，不用 `deleted_at` 软删除，用 `is_active`（见 0.5.4）
- 历史合同引用的公司即使 `is_active=false` 也必须能正常查询显示

### 3.3 tax_id（统一社会信用代码）的处理

**格式**：18 位大写字母和数字组合，如 `91330782MA2EEHAU50`

**约束**：
- 不强制唯一（允许 NULL）——历史数据中部分公司无税号
- 但**有值时必须唯一**（见 3.4 部分唯一索引）
- 作为重复检测的最强信号（`create_company` workflow 会优先用 tax_id 查重）

**导入策略**：
- 档案里没有税号的记录直接导入（NULL）
- 之后如果调工商 API 补齐了 tax_id，更新即可
- 两条 tax_id 相同的记录是明确的重复（见 `detect_duplicates.py` 规则）

### 3.4 索引与约束

```sql
-- 正式名：对活跃公司唯一
CREATE UNIQUE INDEX idx_companies_formal_name_active
  ON companies(formal_name) WHERE is_active = true;

-- 税号：有值时唯一（不包含 NULL）
CREATE UNIQUE INDEX idx_companies_tax_id
  ON companies(tax_id) WHERE tax_id IS NOT NULL;

-- 模糊搜索（pg_trgm）
CREATE INDEX idx_companies_formal_name_trgm
  ON companies USING gin(formal_name gin_trgm_ops);

-- 业务查询常用
CREATE INDEX idx_companies_type ON companies(company_type) WHERE is_active = true;
CREATE INDEX idx_companies_active ON companies(is_active);
```

### 3.5 说明

- **软关联**: contracts 表不强制要求每个甲方/乙方都在此表注册
- 此表作为逐步规范化的目标，Phase 2 逐步推进
- **新增公司走 `create_company` workflow**（见 workflows.md 11 节），不允许直接 INSERT

---

## 4. company_aliases（公司简称表）

支持"美远 → 美远贸易有限公司"这类映射。**简称既有系统自动生成的，也有业务员手工维护的，还有 AI 从对话中学习的。**

### 4.1 字段定义

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| id | uuid | Y | 主键 |
| company_id | uuid | Y | 正式公司 ID（FK → companies）|
| alias | varchar(100) | Y | 简称文本 |
| alias_type | enum | Y | `common`（全局通用）/ `user_specific`（仅某用户有效）|
| specific_user_id | uuid | N | 特定用户（user_specific 类型必填）|
| confidence | decimal(3,2) | Y | 置信度（0-1.0），默认 1.0 |
| source | enum | Y | 来源（见 4.2）|
| generator_version | varchar(10) | N | 自动生成算法版本号（如 `v1.0`）；source=auto_generated 时必填 |
| created_at | timestamptz | Y | |
| created_by | uuid | N | 创建者（手工创建时必填；系统自动生成时为 NULL）|
| deleted_at | timestamptz | N | 软删除时间（NULL = 未删除）|
| deleted_by | uuid | N | 软删除执行人 |
| deleted_reason | text | N | 删除原因 |

### 4.2 source 枚举值（v0.7 扩展）

| source 值 | 含义 | 时机 | 典型数量 |
|----------|------|------|---------|
| `auto_generated` | 系统根据全名自动生成 | 创建公司时（`generate_aliases` 函数）| 每公司 2-3 个 |
| `manual` | 业务员手工追加 | 创建公司时 / 后续维护 | 每公司 0-3 个 |
| `disambiguation` | AI 反问后业务员选择的结果自动沉淀 | 运行期对话中 | 初期少，运行后累积 |
| `promoted` | `disambiguation` 类被多次使用后升格为通用 | 定时任务（Phase 2）| Phase 2 |
| `imported` | 从历史系统/xlsx 批量导入 | W1 建库时一次性 | 首次导入使用 |

**规则**：
- 所有简称无论来源，**查询匹配时同等对待**（不因来源不同而降权）
- `confidence` 字段可为不同来源设不同默认值：auto_generated=0.9、manual=1.0、disambiguation=0.85、promoted=0.95
- 业务员可以删除任何 source 的简称（走 `delete_alias` workflow，软删除）
- 误删可通过"恢复"workflow 找回

### 4.3 约束

- **(company_id, alias, alias_type, specific_user_id) 对活跃记录唯一**
  ```sql
  CREATE UNIQUE INDEX idx_company_aliases_unique_active
    ON company_aliases(company_id, alias, alias_type, COALESCE(specific_user_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE deleted_at IS NULL;
  ```
- `alias_type = 'user_specific'` 时 `specific_user_id` 必填，否则必空
- `source = 'auto_generated'` 时 `generator_version` 必填，`created_by` 可空
- `source = 'manual'` 时 `created_by` 必填
- `deleted_at IS NOT NULL` 时 `deleted_by`、`deleted_reason` 必填

### 4.4 索引

```sql
-- 精确匹配（最高频）
CREATE INDEX idx_company_aliases_alias
  ON company_aliases(alias)
  WHERE deleted_at IS NULL;

-- 反查某公司的所有简称
CREATE INDEX idx_company_aliases_company
  ON company_aliases(company_id)
  WHERE deleted_at IS NULL;

-- user_specific 快速匹配
CREATE INDEX idx_company_aliases_user_specific
  ON company_aliases(specific_user_id, alias)
  WHERE deleted_at IS NULL AND alias_type = 'user_specific';

-- 模糊匹配兜底（pg_trgm）
CREATE INDEX idx_company_aliases_alias_trgm
  ON company_aliases USING gin(alias gin_trgm_ops)
  WHERE deleted_at IS NULL;
```

### 4.5 生成逻辑见附录 A

完整的简称自动生成规则（剥除后缀、地理前缀识别、业务后缀反复剥离等）详见文档末尾附录 A。

---

## 5. brands（品牌表）

### 5.1 字段定义

| 字段名 | 类型 | 必填 | 含义 | 约束 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | PK, default gen_random_uuid() |
| formal_name | varchar(100) | Y | 正式品牌名 | 部分唯一索引（is_active=true 时唯一） |
| is_active | boolean | Y | 是否激活 | 默认 true |
| notes | text | N | 备注（如"等业务员补全提货地"等元信息） | |
| created_at, updated_at, version | | Y | 通用审计字段 | |

### 5.2 索引

```sql
-- 正式名对活跃品牌唯一
CREATE UNIQUE INDEX idx_brands_formal_name_active
  ON brands(formal_name) WHERE is_active = true;

-- 模糊搜索
CREATE INDEX idx_brands_formal_name_trgm
  ON brands USING gin(formal_name gin_trgm_ops);
```

### 5.3 种子数据（34 个品牌，全量）

W1 建库时通过 `import_brands.py` 从 `data-import/brands_master.xlsx` 导入。完整品牌清单见 `data-import/brands_master.xlsx`，分类如下：

**核心活跃品牌（历史合同高频出现）**:
- 三房巷、万凯、大连逸盛、海南逸盛、华润、华润圆粒子
- 百宏（细分为"瓶级百宏"和"有光百宏"两个独立品牌）
- 仪征中石化、富海、昊源
- 恒力（独立品牌）、进口大有光（独立品牌）、膜级再生

**长尾品牌（合同少或新增）**:
- 安化、佳宝、宝生、古纤道、三维、远纺、安邦
- 华润PETG、华宏、盛虹、华亚、恒逸、华逸
- 汉江、天圣、森楷、国信、乐凯、逸鹏、逸达

**待业务员补全数据的品牌**（13 个无提货地、8 个无型号，已在 `brands_master.xlsx` 的 `notes` 列标注）：
- 这些品牌允许导入（`is_active=true`），但创建合同时如果没有对应提货地/型号，会有警告
- 业务员日常使用中遇到时，通过 `create_delivery_location` / `create_product` workflow 补充

### 5.4 数据来源说明

本表的 34 个品牌来源于客户的真实 PostgreSQL 主数据（2026-04-21 导出）。**v0.8 之前的 schema 文档只列了 12 个历史合同里出现过的品牌，是不完整的**——实际业务中有 34 个品牌，部分品牌虽然历史合同少但仍是有效供应商/品牌方。

---

## 5b. 历史品牌名映射（W1 历史合同导入用）

历史 250 条合同里使用的品牌名与新主数据可能不一致，导入时需要映射：

| 历史合同里的品牌名 | 新标准品牌名 | 备注 |
|-------------------|-------------|------|
| 百宏 | **瓶级百宏** | 默认映射；如果合同型号是"大有光"则映射到"有光百宏"|
| 仪征 | **仪征中石化** | |
| 恒力大有光 | **恒力** | "大有光"作为型号录入到 product_model 字段 |
| 大连 | **大连逸盛** | 业务员日常简称 |
| 海南 | **海南逸盛** | 业务员日常简称 |
| 三房 | **三房巷** | 业务员日常简称 |

**映射逻辑伪码**（W1 导入脚本 `scripts/import_historical_contracts.py` 中实现）:
```python
BRAND_NAME_MIGRATION = {
    "百宏": "瓶级百宏",  # 默认; 见特殊规则
    "仪征": "仪征中石化",
    "恒力大有光": "恒力",
    "大连": "大连逸盛",
    "海南": "海南逸盛",
    "三房": "三房巷",
}

def migrate_brand_name(old_name: str, product_model: str) -> str:
    # 特殊规则: 百宏 + "大有光"型号 → 有光百宏
    if old_name == "百宏" and product_model == "大有光":
        return "有光百宏"
    return BRAND_NAME_MIGRATION.get(old_name, old_name)
```

如果历史合同里出现了不在上表的品牌名，导入脚本必须**报错并停止**，由业务员人工处理（不允许悄悄创建新品牌）。

---

## 6. products（型号表）

### 6.1 字段定义

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| id | uuid | Y | 主键 |
| brand_id | uuid | Y | 所属品牌（FK → brands）|
| model_code | varchar(100) | Y | 型号编码 |
| is_active | boolean | Y | 默认 true |
| notes | text | N | 备注 |
| created_at, updated_at, version | | Y | 通用审计字段 |

### 6.2 唯一约束

```sql
-- 同一品牌下型号编码唯一（活跃记录）
CREATE UNIQUE INDEX idx_products_brand_model_active
  ON products(brand_id, model_code) WHERE is_active = true;

CREATE INDEX idx_products_brand ON products(brand_id) WHERE is_active = true;
CREATE INDEX idx_products_model_trgm
  ON products USING gin(model_code gin_trgm_ops);
```

**注意**：UNIQUE 是 `(brand_id, model_code)` 的组合，不是 `model_code` 单独唯一。原因是同一型号编码可能在不同品牌下使用：
- "CR8816" 同时在"华润"和"华润圆粒子"下存在
- "YS-W01" 同时在"大连逸盛"和"海南逸盛"下存在（同一集团）
- "大有光"作为通用品类，在 15 个品牌下存在
- "水料"、"油料"作为通用品类，在 4 个品牌下存在

### 6.3 种子数据（45 个型号）

W1 建库时通过 `import_products.py` 从 `data-import/products_master.xlsx` 导入。完整清单见 xlsx，按品牌分组：

| 品牌 | 型号 |
|------|------|
| 三房巷 | CZ302, CZ318, CZ328, CZ333 |
| 万凯 | WK-801, WK-811, WK-821, WK-851, WK-881 |
| 大连逸盛 | YS-W01, YS-Y01, YS-C01 |
| 海南逸盛 | YS-W01, YS-Y01, YS-C01 |
| 华润 | CR8816, CR8828, CR8839, CR8863 |
| 华润圆粒子 | CR8816, CR8863 |
| 仪征中石化 | 水料, 油料 |
| 昊源 | 水料, 油料 |
| 汉江 | 水料, 油料 |
| 瓶级百宏 | 水料, 油料 |
| 华润PETG | PETG |
| 通用品类"大有光" | 在 15 个品牌下存在：佳宝、古纤道、恒力、三维、安邦、华宏、盛虹、华亚、恒逸、华逸、有光百宏、天圣、森楷、国信、乐凯 |

### 6.4 关于"大有光" / "水料" / "油料"

这三个是**业内通用品类**，不是具体品牌专属型号。在数据库设计上两种方案：

- **方案 A（已选）**：每个品牌下挂自己的"大有光"/"水料"/"油料"记录，数据冗余但简单
- 方案 B（未选）：抽出 product_category 字段，型号 = brand + category 组合

选 A 的原因：业务员习惯说"佳宝大有光"、"恒力大有光"，把"大有光"视为型号；改方案会增加业务员适应成本。AI 在反问时如果用户只说"大有光"必须问"哪个品牌的大有光"。

### 6.5 待业务员补全

8 个品牌当前无型号数据：安化、膜级再生、宝生、进口大有光、远纺、富海、逸鹏、逸达。

业务员日常使用中遇到时通过 `create_product` workflow 补充。

---

## 7. delivery_locations（提货地表）

### 7.1 重大变更（v0.8）

⚠️ **此表在 v0.8 重构**。之前设计为"全局共享提货地"，现改为"**品牌专属提货地**"——每条记录必须挂在一个品牌下。

**业务原因**：实际数据中，"江阴"这个地名在 7 个品牌下各自存在（三房巷在江阴有 4 个不同仓、华润圆粒子在江阴有 1 个仓、有光百宏 1 个、瓶级百宏 1 个）。它们物理上可能在同一个区域，但**业务上是独立的提货点**：地址不同、仓储方不同、提货流程不同。

业务员说"江阴提"在不知道品牌时是有歧义的，必须先确定品牌。

### 7.2 字段定义

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| id | uuid | Y | 主键 |
| brand_id | uuid | Y | 所属品牌（FK → brands）|
| location_name | varchar(50) | Y | 业务员日常简称（如"江阴"、"乍浦"）|
| full_address | text | Y | 完整详细地址 |
| district | varchar(100) | N | 行政区（如"江苏省无锡市江阴市"）|
| lng | decimal(10,6) | N | 经度 |
| lat | decimal(10,6) | N | 纬度 |
| adcode | varchar(10) | N | 国家行政区编码（如 "320281"）|
| citycode | varchar(10) | N | 国家城市编码（如 "320200"）|
| sort_order | int | Y | 排序权重（默认 0；数大的优先显示）|
| is_active | boolean | Y | 默认 true |
| notes | text | N | 备注 |
| created_at, updated_at, version | | Y | 通用审计字段 |

### 7.3 索引与约束

```sql
-- 同一品牌下,(location_name + full_address) 组合唯一
-- 这样允许同一品牌在同一地名有多个不同地址的仓库
CREATE UNIQUE INDEX idx_locations_brand_loc_addr_active
  ON delivery_locations(brand_id, location_name, full_address)
  WHERE is_active = true;

-- 反查某品牌的所有提货地
CREATE INDEX idx_locations_brand_active
  ON delivery_locations(brand_id, sort_order DESC)
  WHERE is_active = true;

-- 模糊搜索 location_name (业务员说"江阴"时跨品牌搜索)
CREATE INDEX idx_locations_name_trgm
  ON delivery_locations USING gin(location_name gin_trgm_ops)
  WHERE is_active = true;
```

**注意去掉了 `name UNIQUE`**：v0.7 之前设计为 `name UNIQUE`，会导致只能存一个"江阴"。新设计允许多个"江阴"，但 `(brand_id, location_name, full_address)` 三元组必须唯一（防止同品牌重复录入相同仓库）。

### 7.4 种子数据（55 个提货地）

W1 建库时通过 `import_delivery_locations.py` 从 `data-import/delivery_locations_master.xlsx` 导入。每条记录都关联到具体品牌。

**关键统计**（基于 55 条数据）：
- 海南逸盛 15 个提货地（最多，全国布局）
- 大连逸盛 9 个
- 三房巷 4 个（都在江阴，不同地址）
- 华润 4 个、万凯 3 个
- 其他品牌 1-2 个
- 13 个品牌（佳宝、宝生等）暂无提货地

### 7.5 AI 处理"江阴提"的逻辑（业务规则）

业务员说"江阴提"或"在江阴提货"时，AI 必须按以下逻辑处理：

```
情况 A: 上下文已确定品牌（如对话中已经说了"三房巷"）
  → fuzzy_match_location(brand_id=三房巷, query="江阴")
  → 返回 4 条结果（三房巷在江阴的 4 个仓库）
  → 按 sort_order 降序展示，让业务员选
  → 如果 4 条 sort_order 都为 0,反问"具体哪个仓库?"
  → 如果 1 条 sort_order 明显高于其他,可默认选它,但需展示给业务员确认

情况 B: 上下文未确定品牌
  → AI 必须先反问品牌
  → "你说的'江阴提',是哪个品牌？三房巷/华润圆粒子/有光百宏/瓶级百宏 在江阴都有提货地"
  → 业务员选定品牌后,再走情况 A
```

**禁止的行为**：
- ❌ AI 不能自己猜品牌（哪怕只有 1 个品牌在某地有仓也不行）
- ❌ AI 不能跨品牌返回提货地（例如返回"三房巷江阴 + 华润江阴"让业务员选）
- ❌ AI 不能默认 sort_order 最高的提货地直接执行写操作（必须让业务员确认）

这个逻辑在 `app/tools/queries/fuzzy_match_location.py` 实现，并在 `business-defaults.md` 中文档化。

### 7.6 contracts.delivery_location_id 的语义变更

之前 `contracts.delivery_location_id` 指向全局提货地。**v0.8 后语义变为指向"品牌专属提货地"**。

强约束：
```sql
-- 合同的提货地必须属于合同的品牌
-- 由应用层在 plan() 阶段校验,不在 DB 层 CHECK 约束(跨表 CHECK 复杂)
```

应用层伪码：
```python
async def validate_contract_location(contract):
    location = await db.get(DeliveryLocation, contract.delivery_location_id)
    if location.brand_id != contract.brand_id:
        raise ValidationError(
            f"提货地 {location.location_name} 属于品牌 {location.brand.formal_name},"
            f"不能用于品牌 {contract.brand.formal_name} 的合同"
        )
```

---

## 8. brand_aliases / product_aliases（品牌简称 / 型号简称）

### 8.1 设计原则

简称表是 AI 对话系统的核心：业务员说"302"，系统得知道这是"三房巷 CZ302"。简称表用 **(brand_id 或 product_id) + alias** 的关联方式，**不在主表上加字段**——这样一个型号可以挂多个简称，简称查询走索引精确匹配。

**核心规则**：
- 简称表允许同一 alias 多行（即"歧义"），由 `is_ambiguous` 字段标记
- AI 看到 `is_ambiguous=true` 或精确查询返回多行时，**强制反问业务员补充上下文**（品牌）
- 完整型号编码（如 `CZ302`）也作为一条简称入表，AI 不区分"完整名"和"简称"，统一查 aliases

### 8.2 brand_aliases（品牌简称表）

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| id | uuid | Y | 主键 |
| brand_id | uuid | Y | 正式品牌 ID（FK → brands）|
| alias | varchar(100) | Y | 简称（如"三房"、"恒力"）|
| is_ambiguous | boolean | Y | 是否歧义（多品牌共用同一 alias），默认 false |
| source | enum | Y | `imported` / `manual` / `disambiguation` |
| confidence | decimal(3,2) | Y | 置信度，默认 1.0 |
| notes | text | N | 说明（如"行业内对逸盛大化的简称"）|
| created_at | timestamptz | Y | |
| created_by | uuid | N | 创建人（FK → users，imported 时为空）|

**约束**：
- UNIQUE (brand_id, alias) ——同一品牌下同 alias 不重复
- 不要 UNIQUE (alias) ——允许跨品牌歧义

**初始数据**：46 条已 review 通过的简称（详见 `data-import/brand_aliases_final.xlsx`），全部 `source='imported'`、`is_ambiguous=false`（业务员 review 时已删除所有歧义简称）。

### 8.3 products 表的 UNIQUE 调整说明

> 这里复述 v0.8 第 6 节的关键变更：products 表的 UNIQUE 约束已从 `(model_code)` 改为 `(brand_id, model_code)`。这是 product_aliases 表设计的前提——同一个 `model_code`（如 `CR8816`）可以在多个品牌下存在，所以简称解析必须返回 `(brand_id, product_id)` 二元组才能定位到唯一型号记录。

### 8.4 product_aliases（型号简称表）

| 字段名 | 类型 | 必填 | 含义 |
|--------|------|------|------|
| id | uuid | Y | 主键 |
| product_id | uuid | Y | 正式型号 ID（FK → products）|
| brand_id | uuid | Y | 冗余存储，便于查询过滤（FK → brands）|
| alias | varchar(100) | Y | 简称（如"302"、"大有光"）|
| is_ambiguous | boolean | Y | 是否歧义（多个 product 共用同一 alias），默认 false |
| source | enum | Y | `imported` / `manual` / `disambiguation` |
| confidence | decimal(3,2) | Y | 置信度，默认 1.0 |
| notes | text | N | 说明（如"15 个品牌共享，必须反问品牌"）|
| created_at | timestamptz | Y | |
| created_by | uuid | N | 创建人（FK → users，imported 时为空）|

**约束**：
- UNIQUE (product_id, alias) ——同一型号下同 alias 不重复
- **不要 UNIQUE (alias)** ——大有光、水料、油料、8816 等本身就是多 product 共用
- INDEX (alias) ——简称查询主路径
- INDEX (brand_id, alias) ——已知品牌时按品牌过滤简称查询

**关键设计：brand_id 冗余存储**
product_aliases 同时存 `product_id` 和 `brand_id`（虽然 product 已经隐含 brand）。这样 AI 处理对话时常用查询是：
```sql
-- 已知品牌 + 简称，定位唯一型号
SELECT product_id FROM product_aliases
WHERE brand_id = ? AND alias = ?;
```
不用 JOIN products 表，性能更好。

### 8.5 product_aliases 初始数据

来源：`data-import/product_aliases_master.xlsx`，77 条简称。

**生成规则**：
1. **完整型号编码作为简称**：每个 model_code（CZ302、CR8816、WK-801、YS-W01、PETG）入表
   - 跨品牌共享的编码（CR8816/CR8863/YS-W01/Y01/C01）：每个品牌一行，标 `is_ambiguous=true`
2. **纯数字 / 字母简称（业务员口语化）**：
   - CZ318/302/328/333 → 318/302/328/333 （三房巷唯一，非歧义）
   - CR8828/8839 → 8828/8839 （华润唯一，非歧义）
   - **CR8816/8863 → 8816/8863** （华润 + 华润圆粒子共用，标 `is_ambiguous=true`）
   - WK-801~881 → 801/811/821/851/881 （万凯唯一）+ WK801/WK811/... 去横杠形式
   - **YS-W01/Y01/C01 → W01/Y01/C01 + YSW01/YSY01/YSC01** （大连/海南逸盛共用，标 `is_ambiguous=true`）
3. **多品牌共享品类型号名**（强制歧义）：
   - **大有光**：15 个品牌都有该型号，每个品牌一行，全部 `is_ambiguous=true`
   - **水料**：4 个品牌（昊源、仪征中石化、汉江、瓶级百宏）都有
   - **油料**：4 个品牌（昊源、仪征中石化、汉江、瓶级百宏）都有

**统计**：
- 总行数：77
- 非歧义简称：28 行
- 歧义简称（is_ambiguous=true）：49 行
- 出现多次的 alias key：16 个

### 8.6 AI 处理简称查询的标准逻辑

业务员对话中提到型号时，AI 按以下流程定位：

```
输入：业务员口语 → 提取型号关键词 keyword
  
Step 1: 在 product_aliases 表精确匹配 alias = keyword
  
  Case A: 精确匹配 1 条 + is_ambiguous=false
    → 直接定位 (brand_id, product_id)，无需反问 ✅
    
  Case B: 精确匹配多条 OR is_ambiguous=true
    → 检查对话上下文是否已有品牌 brand_context：
       ├─ 有 → SQL 加 WHERE brand_id = brand_context 过滤
       │      ├─ 命中 1 条 → 定位成功 ✅
       │      └─ 命中 0 条 → 反问"品牌 X 下没有 keyword 这个型号，您是不是说错了？"
       └─ 无 → 反问"您说的'keyword'是哪个品牌的？候选：A / B / C..."
    
  Case C: 精确匹配 0 条
    → fuzzy match products.model_code（pg_trgm 相似度 > 0.6）
    → 仍无 → 反问"找不到 keyword 这个型号，您能再说一遍或拼写一下吗？"
```

**特殊场景：跨简称表查询的优先级**
当业务员说"开 100 吨大有光"时，"大有光"既可能在 product_aliases 命中 15 条歧义记录，也可能在 brand_aliases 命中（如果未来某品牌起了"大有光"的简称）。AI 优先查 product_aliases（"大有光"在业务语境是型号词），反问用品牌候选列表辅助。

### 8.7 简称冲突检测（运维 SQL）

定期跑这条 SQL 检查简称表健康度：

```sql
-- 检测 brand_aliases 中是否出现跨品牌同名简称
SELECT alias, COUNT(DISTINCT brand_id) AS brand_count, ARRAY_AGG(brand_id) AS brand_ids
FROM brand_aliases
WHERE deleted_at IS NULL  -- brand_aliases 走软删除
GROUP BY alias
HAVING COUNT(DISTINCT brand_id) > 1;

-- 检测 product_aliases 中歧义但未标 is_ambiguous=true 的脏数据
SELECT alias, COUNT(*) AS cnt, BOOL_OR(is_ambiguous) AS any_marked
FROM product_aliases
WHERE deleted_at IS NULL
GROUP BY alias
HAVING COUNT(*) > 1 AND BOOL_OR(is_ambiguous) = false;
```

后者出现非空结果就是 BUG：要么标记缺失，要么数据导入有问题。

---

## 9. delivery_orders（提货工单表）

### 9.1 用途

记录每次客户发起的提货事件，对应销售类合同（`sales`, `brokering_sales`, `lending_sales`）。

### 9.2 业务流程定位

```
销售合同 ──(1:N)──→ 提货工单 ──(1:N)──→ 车辆调度 ──(N:1)──→ 提货委托 ──(N:1)──→ 采购合同
                                        每车一条                 一个工单可能拆 1~N 个委托
```

一个销售合同可被多次提货，每次建立一条工单。工单是整个提货链的起点（所有提货都由销售合同发起）。

### 9.3 样本数据特征

- 64 条工单记录
- 1 张工单对应 1~5 条车辆调度（平均 1.23）
- 1 张工单对应 1~5 条提货委托（平均 1.18，分别指向不同采购合同）
- 工单数量 100% 等于对应所有委托数量之和 ✅

### 9.4 字段定义

| 字段名 | 类型 | 必填 | 含义 | 说明 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | |
| order_number | varchar(50) | Y | 工单编号 | 部分唯一索引 |
| status | enum | Y | 工单状态 | `normal` / `cancelled`，默认 normal |
| sales_contract_id | uuid | Y | 销售合同 ID | FK → contracts |
| quantity_tons | decimal(12,3) | Y | 提货数量（吨） | > 0；工单累计 ≤ 合同数量 |
| unit_price | decimal(10,2) | Y | 单价（元/吨） | **必须等于销售合同的 unit_price**（见下说明）|
| extra_fee | decimal(12,2) | N | 额外费用（元） | 特殊型号加价、仓库差价、其他一次性费用等 |
| extra_fee_notes | text | N | 额外费用说明 | 文字描述（如"328 型号 11 吨 ×100 = 1,100"）|
| customer_name_snapshot | varchar(200) | Y | 对应客户名称（快照） | 冗余自合同，打印凭证用 |
| our_subject_snapshot | varchar(200) | Y | 对应主体公司（快照） | 冗余自合同 |
| customer_delivery_letter_url | text | N | 客户提货委托书附件 URL | |
| receipt_confirmation_url | text | N | 收货确认函附件 URL | |
| notes | text | N | 备注 | |
| created_by, created_at, updated_by, updated_at, version | | Y | 通用审计字段 | |
| deleted_at, deleted_by, deleted_reason | | N | 软删除字段 | 见 0.5 |

**unit_price 的强约束**（非常重要）:

合同的数量和单价是整个价格体系的真源，**不可被下游工单绕过**：

- 创建工单时，unit_price 从销售合同自动拷贝，**业务员不能手工输入和修改**
- 合同单价修改了 → 对应所有未完结工单的单价同步更新（需要走修改合同 workflow）
- 审计规则 `order_price_mismatch_check` 监测 "工单单价 ≠ 合同单价"（严重错误）
- 如果实际结算价格需要偏离合同，**必须先修改合同**，不能在工单上直接改
- `extra_fee` 不是"调整货款单价"的手段，而是记录一次性的额外费用（特殊型号加价、仓库差价、运费调整等），业务含义上独立于单价

**与销售合同的数量守恒**（审计规则会检查）:
```
对某销售合同 C:
  SUM(delivery_orders.quantity_tons WHERE sales_contract_id = C AND status='normal' AND deleted_at IS NULL) 
  ≤ C.quantity_tons
```

**注意旧数据的"车辆调度"字段不迁移**：原飞书表中 delivery_orders.车辆调度 是逗号分隔字符串（如 `DD-20260405-018,DD-20260405-017,DD-20260405-019`）。新系统**反向关联**——车辆调度表指向工单（有 `delivery_order_id` 字段），工单表里不再存这个信息。

### 9.5 索引

```sql
CREATE INDEX idx_orders_status ON delivery_orders(status);
CREATE INDEX idx_orders_contract ON delivery_orders(sales_contract_id);
CREATE INDEX idx_orders_created_at ON delivery_orders(created_at DESC);
CREATE INDEX idx_orders_deleted_at ON delivery_orders(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE UNIQUE INDEX idx_orders_number_active 
  ON delivery_orders(order_number) WHERE deleted_at IS NULL;
```

---

## 10. delivery_delegations（提货委托表）

### 10.1 用途

记录每次向上游发起的提货委托，对应采购类合同（`purchase`, `brokering_purchase`, `lending_purchase`）。

### 10.2 业务流程定位

委托由工单驱动生成。一张工单可能对应多个委托（因为同一次提货可能来自不同采购合同）。

### 10.3 样本数据特征

- 58 条委托记录
- 1 张工单对应 1~5 条委托
- 委托数量 × 对应工单数量对账 100% ✅

### 10.4 字段定义

| 字段名 | 类型 | 必填 | 含义 | 说明 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | |
| delegation_number | varchar(50) | Y | 委托编号 | 部分唯一索引 |
| status | enum | Y | 委托状态 | `normal` / `cancelled`，默认 normal |
| source_order_id | uuid | Y | 来源工单 ID | FK → delivery_orders |
| purchase_contract_id | uuid | Y | 采购合同 ID | FK → contracts |
| quantity_tons | decimal(12,3) | Y | 委托数量（吨） | > 0 |
| unit_price | decimal(10,2) | Y | 单价（元/吨） | **必须等于采购合同的 unit_price**（同工单的强约束）|
| extra_payment | decimal(12,2) | N | 额外支付金额（元） | 采购侧的额外费用 |
| extra_payment_notes | text | N | 额外支付说明 | |
| supplier_name_snapshot | varchar(200) | Y | 对应供应商名称（快照） | 冗余自合同 |
| our_subject_snapshot | varchar(200) | Y | 对应主体公司（快照） | |
| notes | text | N | 备注 | |
| created_by, created_at, updated_by, updated_at, version | | Y | 通用审计字段 | |
| deleted_at, deleted_by, deleted_reason | | N | 软删除字段 | |

**unit_price 的强约束**: 同工单，unit_price 从采购合同自动拷贝不可手改，审计规则 `delegation_price_mismatch_check` 监测偏离。

**数量守恒约束**（审计规则）:
```
对某工单 O:
  SUM(delegations.quantity_tons WHERE source_order_id=O AND status='normal' AND deleted_at IS NULL)
  = O.quantity_tons
  （允许 0.001 吨误差）

对某采购合同 C:
  SUM(delegations.quantity_tons WHERE purchase_contract_id=C AND status='normal' AND deleted_at IS NULL)
  ≤ C.quantity_tons
```

### 10.5 索引

```sql
CREATE INDEX idx_delegations_status ON delivery_delegations(status);
CREATE INDEX idx_delegations_order ON delivery_delegations(source_order_id);
CREATE INDEX idx_delegations_contract ON delivery_delegations(purchase_contract_id);
CREATE INDEX idx_delegations_created_at ON delivery_delegations(created_at DESC);
CREATE INDEX idx_delegations_deleted_at ON delivery_delegations(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE UNIQUE INDEX idx_delegations_number_active 
  ON delivery_delegations(delegation_number) WHERE deleted_at IS NULL;
```

---

## 11. dispatches（车辆调度表）

### 11.1 用途

记录每一车实际发车的详细信息：司机、车牌、装载量、提货时间、**实际提了什么货**。调度是工单到委托之间的中枢：**工单 ↔ 调度 ↔ 委托**。

### 11.2 业务说明

**核心理念**: 调度表记录**物流事实**，不关心价格。价格由工单/委托按合同单价结算。

- 一个工单可拆 1~N 车（每车 30-33 吨左右，所以大批量要拆车）
- 调度有两种模式：**个人司机**（填司机姓名、身份证、手机）或 **物流公司**（车牌号字段填物流公司名）
- 调度的品牌/型号/提货地是**实际物流记录**，可能与合同约定不同（业务允许调整，不影响价格）

### 11.3 调度记录的拆分规则（重要）

**一条调度记录 = 同工单 + 同提货地 + 同品牌 + 同型号**的一车货。

**提货地 / 品牌 / 型号 三个维度任一不同，必须拆成独立调度记录**。

拆分场景举例：

| 场景 | 工单（约定） | 实际提货情况 | 调度记录数 |
|------|------------|------------|----------|
| 单一 | 33 吨，三房 302，江阴 | 一车 33 吨 | 1 条 |
| 多型号 | 33 吨，三房，江阴 | 22 吨 302 + 11 吨 328 | 2 条 |
| 多品牌 | 33 吨，三房，江阴 | 22 吨三房 + 11 吨万凯（品牌调整）| 2 条 |
| 多提货地 | 66 吨，三房 302 | 33 吨江阴 + 33 吨海宁 | 2 条 |
| 全换维度 | 33 吨，三房 302 江阴 | 22 吨三房 302 江阴 + 11 吨万凯 318 海宁 | 2 条 |

**业务原因**：
- 每条调度最终都会输出一份"提货委托书"作为凭证，不同提货地/品牌/型号的凭证必须独立
- 可能从不同上游采购合同提货，需要对应不同的提货委托

**系统价格处理**：品牌/型号变化**不影响价格**。所有提货量最终按合同单价结算。这让调度可以灵活调整物流，不牵动财务。

### 11.4 合同约定 vs 实际调度的差异

合同约定品牌是三房，实际调度拉了万凯——这是合法的业务行为（可能因为库存紧张或调货方便）。

**但审计系统会发现并提醒**：
- `dispatch_brand_deviation_check` - 调度品牌 ≠ 合同品牌 → 提醒（非错误）
- `dispatch_product_deviation_check` - 调度型号 ≠ 合同型号 → 提醒
- `dispatch_location_deviation_check` - 调度提货地 ≠ 合同提货地 → 提醒

这些提醒不是错误，只是让业务员/财务知情（可能涉及后续对账或税务处理）。

### 11.5 编号规则

`DD-YYYYMMDD-NNN` 或 `DD-YYYYMMDD-NNN-X`（按拆分规则需要拆时）

例：
- `DD-20260405-001`（工单不需要拆）
- `DD-20260405-001-A`, `DD-20260405-001-B`（同工单拆了）

### 11.6 字段定义

| 字段名 | 类型 | 必填 | 含义 | 说明 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | |
| dispatch_number | varchar(50) | Y | 调度编号 | 部分唯一索引 |
| delivery_order_id | uuid | Y | 关联提货工单 | FK → delivery_orders（一条调度挂一个工单）|
| delegation_id | uuid | N | 关联提货委托 | FK → delivery_delegations（业务上后填）|
| dispatch_mode | enum | Y | 调度方式 | `driver`（个人司机）/ `logistics`（物流公司）|
| driver_name | varchar(50) | N | 司机姓名 | driver 模式填 |
| driver_id_number | varchar(30) | N | 身份证号 | driver 模式填，建议加密存储 |
| driver_phone | varchar(20) | N | 手机号 | |
| license_plate | varchar(30) | N | 车牌号 / 物流公司名 | driver 填车牌，logistics 填公司名 |
| load_tons | decimal(12,3) | Y | 本车装载量（吨） | > 0 |
| delivery_date | date | Y | 提货日期 | |
| brand_id | uuid | Y | 实际提货品牌 | FK → brands |
| product_model | varchar(100) | N | 实际提货型号 | |
| delivery_location_id | uuid | Y | 实际提货地 | FK → delivery_locations |
| notes | text | N | 备注 | 一车多货时标注拆分原因 |
| created_by, created_at, updated_by, updated_at, version | | Y | 通用审计字段 | |
| deleted_at, deleted_by, deleted_reason | | N | 软删除字段 | |

**关键说明**：
- `brand_id` / `product_model` / `delivery_location_id` 是**实际物流事实**，不是从合同快照的
- 业务允许这些字段与合同约定不同
- 打印"提货委托书"时使用这些字段的值作为凭证内容

**dispatch_mode 条件必填规则**:
```
IF dispatch_mode = 'driver':
    driver_name, driver_id_number, driver_phone, license_plate 建议都填
    (允许为空，业务上推荐必填但数据库不强制)
    
IF dispatch_mode = 'logistics':
    license_plate 必填（填物流公司名或车队名）
    driver_name, driver_id_number, driver_phone 可为 NULL（物流场景不需要）
```

**数量守恒约束**（审计规则）:
```
对某工单 O:
  SUM(dispatches.load_tons WHERE delivery_order_id=O AND deleted_at IS NULL)
  = O.quantity_tons（允许 0.001 吨误差）

对某委托 D:
  SUM(dispatches.load_tons WHERE delegation_id=D AND deleted_at IS NULL)
  ≤ D.quantity_tons
```

### 11.7 索引

```sql
CREATE INDEX idx_dispatches_order ON dispatches(delivery_order_id);
CREATE INDEX idx_dispatches_delegation ON dispatches(delegation_id);
CREATE INDEX idx_dispatches_date ON dispatches(delivery_date DESC);
CREATE INDEX idx_dispatches_deleted_at ON dispatches(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE UNIQUE INDEX idx_dispatches_number_active 
  ON dispatches(dispatch_number) WHERE deleted_at IS NULL;
```

### 11.8 历史数据导入注意

原飞书调度表字段 "关联提货工单" 是单值字符串，导入时直接映射为 `delivery_order_id`。
原飞书工单表的 "车辆调度" 字段（逗号分隔）**不导入**——这个关联从调度表反向建立。

---

## 12. transactions（流水表）

### 12.1 用途

记录我方（主体 A / 主体 B）与外部公司之间的实际银行流水。**流水表是原始银行数据的忠实映射，是唯一的资金真源**。

### 12.2 核心设计原则

**原则 1：流水表只读，原始字段不可修改**

- 唯一写入途径：`import_transactions` workflow（批量导入银行流水文件）
- 原始字段（流水号、时间、我方、对方、方向、金额）一旦写入永久不变
- 除软删除外，其他字段也不能改
- PG 层通过 REVOKE DELETE 权限 + TRIGGER 多重保护

**原则 2：不在流水表做对账关联**

采用**汇总对账**模式，不对应具体合同：
- 流水表不存 `contract_id` / `delivery_order_id` / `purpose` 等字段
- 对账通过 **视图** 实现：按 `(我方主体 × 对方公司)` 汇总
- 业务员关注的是"这个客户欠我们多少" / "这个供应商我们还欠多少"，这种汇总级问题
- 不做流水到合同的逐笔匹配

**原则 3：公司名规范化靠 company_aliases**

合同里的"张家港辉凡新材料科技有限公司"和流水里的"张家港辉凡新材料"通过 aliases 表映射到同一实体。

### 12.3 样本数据特征

- 713 条记录（2026-02-28 到 2026-03-31）
- 流水号格式：`TZYYYYMMDDNNNNN`（15 位定长，UNIQUE）
- 我方主体：上海瞿谊（697 条）+ 安徽趋易（16 条）—— 与 `subject_a / subject_b` 对应
- 每条记录原始表中同时有"收入"和"支出"字段（其中一个为 0），新系统合并为 `direction + amount`
- 前 10 大对方：浙江塑界新材料、张家港辉凡、台州绿鼎红、江西乾财、安徽葆特等

### 12.4 字段定义

| 字段名 | 类型 | 必填 | 含义 | 说明 |
|--------|------|------|------|------|
| id | uuid | Y | 主键 | |
| transaction_number | varchar(30) | Y | 流水号 | 部分唯一索引；格式 `TZYYYYMMDDNNNNN` |
| transaction_time | timestamptz | Y | 交易时间 | 精确到秒 |
| our_subject_company | enum | Y | 我方主体 | `subject_a` / `subject_b` |
| counterparty_name | varchar(200) | Y | 对方公司名称 | 原始名称（可能与 companies 表不完全一致）|
| direction | enum | Y | 方向 | `in`（收入）/ `out`（支出）|
| amount | decimal(14,2) | Y | 金额（元） | > 0（统一正数存储）|
| imported_at | timestamptz | Y | 导入时间 | 默认 now() |
| imported_by | uuid | Y | 导入人 | FK → users |
| import_batch_id | uuid | N | 导入批次 ID | 便于批次回溯 |
| created_at, updated_at, version | | Y | 通用审计字段 | 注意无 created_by/updated_by（由 imported_by 代替）|
| deleted_at, deleted_by, deleted_reason | | N | 软删除字段 | 见 0.5 |

**注意**：流水表没有 `purpose` / `contract_id` / `order_id` / `delegation_id` / `reconciled` 字段。对账逻辑完全在视图层。

### 12.5 不可修改保护

**方法 1：PG 权限层（阻止物理删除）**
```sql
REVOKE DELETE ON transactions FROM app_user;
```

**方法 2：TRIGGER（阻止原始字段修改）**
```sql
CREATE OR REPLACE FUNCTION prevent_transaction_raw_update()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.transaction_number != OLD.transaction_number OR
     NEW.transaction_time != OLD.transaction_time OR
     NEW.our_subject_company != OLD.our_subject_company OR
     NEW.counterparty_name != OLD.counterparty_name OR
     NEW.direction != OLD.direction OR
     NEW.amount != OLD.amount THEN
    RAISE EXCEPTION '流水原始字段不可修改（流水表只读）';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transactions_raw_immutable
  BEFORE UPDATE ON transactions
  FOR EACH ROW
  EXECUTE FUNCTION prevent_transaction_raw_update();
```

**方法 3：应用层保护**
- 只有 `import_transactions` workflow 能执行 INSERT
- 不提供"修改流水"的 workflow 或 tool
- AI 系统的工具白名单里没有"写流水"能力

**唯一允许的变化**：软删除（`deleted_at` / `deleted_by` / `deleted_reason` 的更新）。

### 12.6 索引

```sql
CREATE UNIQUE INDEX idx_transactions_number_active
    ON transactions(transaction_number) WHERE deleted_at IS NULL;
CREATE INDEX idx_transactions_time ON transactions(transaction_time DESC);
CREATE INDEX idx_transactions_subject ON transactions(our_subject_company);
CREATE INDEX idx_transactions_counterparty_trgm 
    ON transactions USING gin(counterparty_name gin_trgm_ops);
CREATE INDEX idx_transactions_subject_counterparty 
    ON transactions(our_subject_company, counterparty_name);
CREATE INDEX idx_transactions_deleted_at 
    ON transactions(deleted_at) WHERE deleted_at IS NOT NULL;
```

### 12.7 完整 DDL

```sql
CREATE TYPE transaction_direction_enum AS ENUM ('in', 'out');

CREATE TABLE transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 原始银行流水字段（一旦写入不可修改）
    transaction_number varchar(30) NOT NULL,
    transaction_time timestamptz NOT NULL,
    our_subject_company subject_company_enum NOT NULL,
    counterparty_name varchar(200) NOT NULL,
    direction transaction_direction_enum NOT NULL,
    amount decimal(14,2) NOT NULL CHECK (amount > 0),
    
    -- 导入元信息
    imported_at timestamptz NOT NULL DEFAULT now(),
    imported_by uuid NOT NULL REFERENCES users(id),
    import_batch_id uuid,
    
    -- 通用审计 + 软删除
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version int NOT NULL DEFAULT 1,
    deleted_at timestamptz,
    deleted_by uuid REFERENCES users(id),
    deleted_reason text,
    
    CONSTRAINT check_soft_delete_consistency CHECK (
        (deleted_at IS NULL AND deleted_by IS NULL AND deleted_reason IS NULL) OR
        (deleted_at IS NOT NULL AND deleted_by IS NOT NULL AND deleted_reason IS NOT NULL)
    )
);

-- 索引（见 12.6）
-- TRIGGER 见 12.5
-- REVOKE DELETE ON transactions FROM app_user;
```

### 12.8 历史数据导入清洗规则

原飞书"收入"和"支出"两列合并为 `direction + amount`:
```
IF 收入 > 0 AND 支出 = 0:
    direction = 'in', amount = 收入
ELIF 支出 > 0 AND 收入 = 0:
    direction = 'out', amount = 支出
ELSE:
    异常行，单独记录到错误日志，不导入
```

"我方公司名称"映射：
```
"上海瞿谊实业有限公司" → subject_b
"安徽趋易贸易有限公司" → subject_a
其他 → 异常，单独记录
```

导入时批量使用同一个 `import_batch_id`，方便回溯。

---

## 12.9 对账视图（核心）

对账逻辑完全通过视图实现，不在表结构中关联。

### 视图 1：规范化后的流水

通过 company_aliases 把"张家港辉凡新材料"映射到"张家港辉凡新材料科技有限公司"：

```sql
CREATE VIEW v_transactions_normalized AS
SELECT
    t.*,
    COALESCE(
        (SELECT c.formal_name 
         FROM company_aliases ca 
         JOIN companies c ON c.id = ca.company_id
         WHERE ca.alias = t.counterparty_name 
           AND ca.alias_type = 'common'
         LIMIT 1),
        -- 如果 counterparty_name 本身就是 companies.formal_name
        (SELECT c.formal_name FROM companies c 
         WHERE c.formal_name = t.counterparty_name 
         LIMIT 1),
        -- 找不到就用原名
        t.counterparty_name
    ) AS counterparty_formal_name
FROM transactions t
WHERE t.deleted_at IS NULL;
```

### 视图 2：按 (主体 × 对方公司) 汇总流水净额

```sql
CREATE VIEW v_transaction_balance_by_counterparty AS
SELECT
    our_subject_company,
    counterparty_formal_name,
    SUM(CASE WHEN direction = 'in' THEN amount ELSE 0 END) AS total_in,
    SUM(CASE WHEN direction = 'out' THEN amount ELSE 0 END) AS total_out,
    SUM(CASE WHEN direction = 'in' THEN amount ELSE -amount END) AS net_balance,
    COUNT(*) AS transaction_count,
    MIN(transaction_time) AS first_transaction_at,
    MAX(transaction_time) AS last_transaction_at
FROM v_transactions_normalized
GROUP BY our_subject_company, counterparty_formal_name;
```

### 视图 3：按 (主体 × 对方公司) 汇总合同应收应付

```sql
CREATE VIEW v_contract_balance_by_counterparty AS
WITH sales_side AS (
    -- 销售类合同（我方作为卖方，对方是客户 = party_b）
    SELECT
        c.our_subject_company,
        COALESCE(
            (SELECT comp.formal_name FROM company_aliases ca
             JOIN companies comp ON comp.id = ca.company_id
             WHERE ca.alias = c.party_b_name AND ca.alias_type = 'common'
             LIMIT 1),
            c.party_b_name
        ) AS counterparty_formal_name,
        SUM(COALESCE(a.receivable_amount, 0)) AS total_receivable,
        CAST(0 AS decimal(14,2)) AS total_payable
    FROM v_contracts_with_aggregates a
    JOIN contracts c ON c.id = a.id
    WHERE c.our_role IN ('seller', 'lender')
      AND c.our_subject_company IS NOT NULL
    GROUP BY c.our_subject_company, counterparty_formal_name
),
purchase_side AS (
    -- 采购类合同（我方作为买方，对方是供应商 = party_a）
    SELECT
        c.our_subject_company,
        COALESCE(
            (SELECT comp.formal_name FROM company_aliases ca
             JOIN companies comp ON comp.id = ca.company_id
             WHERE ca.alias = c.party_a_name AND ca.alias_type = 'common'
             LIMIT 1),
            c.party_a_name
        ) AS counterparty_formal_name,
        CAST(0 AS decimal(14,2)) AS total_receivable,
        SUM(COALESCE(a.payable_amount, 0)) AS total_payable
    FROM v_contracts_with_aggregates a
    JOIN contracts c ON c.id = a.id
    WHERE c.our_role IN ('buyer', 'borrower')
      AND c.our_subject_company IS NOT NULL
    GROUP BY c.our_subject_company, counterparty_formal_name
)
SELECT
    our_subject_company,
    counterparty_formal_name,
    SUM(total_receivable) AS total_receivable,
    SUM(total_payable) AS total_payable,
    SUM(total_receivable) - SUM(total_payable) AS net_expected
FROM (
    SELECT * FROM sales_side
    UNION ALL
    SELECT * FROM purchase_side
) combined
GROUP BY our_subject_company, counterparty_formal_name;
```

### 视图 4：最终对账视图

合同应收应付 vs 流水实收实付的对比：

```sql
CREATE VIEW v_reconciliation AS
SELECT
    COALESCE(c.our_subject_company, t.our_subject_company) AS our_subject_company,
    COALESCE(c.counterparty_formal_name, t.counterparty_formal_name) AS counterparty_formal_name,
    
    -- 合同应收应付（期望值）
    COALESCE(c.total_receivable, 0) AS total_receivable,
    COALESCE(c.total_payable, 0) AS total_payable,
    COALESCE(c.net_expected, 0) AS net_expected,
    
    -- 流水实际收付
    COALESCE(t.total_in, 0) AS total_received,
    COALESCE(t.total_out, 0) AS total_paid,
    COALESCE(t.net_balance, 0) AS net_actual,
    
    -- 差额：期望 vs 实际
    COALESCE(c.net_expected, 0) - COALESCE(t.net_balance, 0) AS difference,
    
    -- 对账状态分类
    CASE 
        WHEN ABS(COALESCE(c.net_expected, 0) - COALESCE(t.net_balance, 0)) < 1 
            THEN 'balanced'          -- 对平
        WHEN ABS(COALESCE(c.net_expected, 0) - COALESCE(t.net_balance, 0)) < 100 
            THEN 'minor_difference'  -- 微小差额（可能是四舍五入）
        ELSE 'significant_difference' -- 显著差额，需人工核查
    END AS status
    
FROM v_contract_balance_by_counterparty c
FULL OUTER JOIN v_transaction_balance_by_counterparty t
    ON c.our_subject_company = t.our_subject_company
    AND c.counterparty_formal_name = t.counterparty_formal_name;
```

**三种 FULL OUTER JOIN 场景**：
- 合同有，流水没有：客户签了合同还没付款（应收为正，实收为 0）
- 流水有，合同没有：预付款先到、合同未录入、或该对方公司无合同（常见于借款/非业务往来）
- 两者都有：正常对账场景

### 视图的查询示例

```sql
-- 所有差额 > 1000 元的对账问题
SELECT * FROM v_reconciliation 
WHERE status = 'significant_difference' 
  AND ABS(difference) > 1000
ORDER BY ABS(difference) DESC;

-- 主体 B 和"美远贸易"的对账
SELECT * FROM v_reconciliation 
WHERE our_subject_company = 'subject_b'
  AND counterparty_formal_name LIKE '%美远%';

-- 主体 B 所有欠款（实收 < 应收的情况）
SELECT * FROM v_reconciliation
WHERE our_subject_company = 'subject_b'
  AND difference > 0  -- 期望 > 实际 = 对方欠我们
ORDER BY difference DESC;
```

### 性能考量

对账视图涉及多表 JOIN 和 aliases 子查询，数据量大时可能慢。Phase 1 先用 VIEW，Phase 2 如果性能不够：
- 改为 materialized view（物化视图），定时刷新
- 或者加单独的 `reconciliation_cache` 表，通过定时任务更新

目前 250 合同 + 700 流水的数据量，普通 VIEW 足够。

---

## 13. fee_adjustments（费用调整规则表，可选）

### 13.1 用途

记录"特殊型号加价"、"特殊仓库加减价"这类规则，AI 生成工单时可自动计算额外费用。

**Phase 1 可暂时不实现**，业务员手工填写 `extra_fee` 字段并在 `extra_fee_notes` 里说明。Phase 2 再考虑规则化。

---

## 14. 审计表（Audit 三件套）

### 14.1 audit_logs（审计日志）

**用途**：每次执行 Plan（增删改数据）记录一笔完整执行日志。

**写入时机**：`ProposalExecutor.execute()` 在事务内写入。

**特性**：只允许 INSERT + SELECT。

```sql
CREATE TABLE audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid REFERENCES change_proposals(id),
    conversation_id uuid REFERENCES conversations(id),
    message_id uuid REFERENCES messages(id),       -- 触发操作的用户消息
    workflow_name varchar(100) NOT NULL,
    workflow_version varchar(20) NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id),
    operations jsonb NOT NULL,                      -- 执行了哪些 operation
    status varchar(20) NOT NULL,                    -- success / failed / rolled_back
    error_message text,
    executed_at timestamptz NOT NULL,
    duration_ms int
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id, executed_at DESC);
CREATE INDEX idx_audit_logs_plan ON audit_logs(plan_id);
CREATE INDEX idx_audit_logs_workflow ON audit_logs(workflow_name, executed_at DESC);
CREATE INDEX idx_audit_logs_conversation ON audit_logs(conversation_id);

REVOKE UPDATE, DELETE ON audit_logs FROM app_user;
```

### 14.2 change_proposals（操作提案表）

**用途**：存储 AI 为业务员生成的 Plan（操作方案），待确认、审批、执行。

**写入时机**：workflow 的 `plan()` 函数生成方案时。

```sql
CREATE TYPE proposal_status_enum AS ENUM (
    'draft',               -- 草稿（规则校验未通过）
    'pending_confirm',     -- 待用户确认
    'pending_approval',    -- 待审批
    'approved',            -- 审批通过（等待执行）
    'executing',           -- 执行中
    'completed',           -- 执行成功
    'cancelled',           -- 用户取消
    'rejected',            -- 审批拒绝
    'failed'               -- 执行失败
);

CREATE TABLE change_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_name varchar(100) NOT NULL,
    workflow_version varchar(20) NOT NULL,
    params jsonb NOT NULL,                          -- workflow 的输入参数
    operations jsonb NOT NULL,                      -- 待执行的 insert/update/delete 列表
    violations jsonb,                               -- 规则校验违规项
    required_approvers jsonb,                       -- 需要的审批人列表
    status proposal_status_enum NOT NULL DEFAULT 'draft',
    created_by uuid NOT NULL REFERENCES users(id),
    conversation_id uuid REFERENCES conversations(id),
    confirmed_at timestamptz,
    confirmed_by uuid REFERENCES users(id),
    executed_at timestamptz,
    audit_log_id uuid REFERENCES audit_logs(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_proposals_status ON change_proposals(status, created_at DESC);
CREATE INDEX idx_proposals_user ON change_proposals(created_by, created_at DESC);
CREATE INDEX idx_proposals_conversation ON change_proposals(conversation_id);
```

### 14.3 approval_records（审批记录）

**用途**：Plan 需要审批时的审批过程记录。

**写入时机**：Plan 需要审批时为每个审批人创建一条 pending 记录，审批人决定时更新 decision。

```sql
CREATE TYPE approval_decision_enum AS ENUM (
    'pending', 'approved', 'rejected', 'delegated'
);

CREATE TABLE approval_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES change_proposals(id),
    approver_user_id uuid NOT NULL REFERENCES users(id),
    approver_role varchar(50),
    sequence int NOT NULL,                          -- 第几级审批（1/2/3）
    decision approval_decision_enum NOT NULL DEFAULT 'pending',
    comment text,
    decided_at timestamptz,
    card_message_id varchar(100),                   -- 飞书卡片消息 ID
    original_approver_id uuid REFERENCES users(id), -- 请假转移时的原审批人
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_approvals_plan ON approval_records(plan_id);
CREATE INDEX idx_approvals_approver ON approval_records(approver_user_id, decision);
CREATE INDEX idx_approvals_pending ON approval_records(decision) WHERE decision = 'pending';
```

---

## 15. History 表（每个业务表一张）

### 15.1 通用规范

每个业务表（contracts / delivery_orders / delivery_delegations / dispatches / transactions）都有对应的 history 表，结构统一：

```sql
CREATE TABLE <table>_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id uuid NOT NULL,                        -- 指向原表的 id
    op_type varchar(20) NOT NULL,                   -- insert / update / soft_delete / restore
    before_snapshot jsonb,                          -- 操作前完整行（JSON）
    after_snapshot jsonb,                           -- 操作后完整行
    changed_fields text[],                          -- 变更了哪些字段
    changed_at timestamptz NOT NULL DEFAULT now(),
    changed_by uuid REFERENCES users(id),
    audit_log_id uuid REFERENCES audit_logs(id)     -- 关联到审计日志
);
CREATE INDEX idx_<table>_history_record ON <table>_history(record_id, changed_at DESC);
REVOKE UPDATE, DELETE ON <table>_history FROM app_user;
```

具体表：
- `contracts_history`
- `delivery_orders_history`
- `delivery_delegations_history`
- `dispatches_history`
- `transactions_history`

### 15.2 op_type 枚举说明

- `insert` - 新建记录
- `update` - 修改字段
- `soft_delete` - 软删除（deleted_at 填入时间戳）
- `restore` - 恢复误删（deleted_at 置回 NULL）

注意：物理删除（DELETE FROM ...）被 PG 权限阻止，所以不会有 `delete` 类型。

### 15.3 写入规范

**Executor 在事务内显式写入**（不用 DB TRIGGER，便于关联审计上下文）：

```python
async def execute_operation(op, audit_log_id, user_id, db):
    model = get_model_by_table(op.table)
    history_model = get_history_model(op.table)
    
    if op.op_type == "insert":
        record = model(**op.after)
        db.add(record)
        await db.flush()
        # 同事务写 history
        db.add(history_model(
            record_id=record.id,
            op_type='insert',
            before_snapshot=None,
            after_snapshot=record.to_dict(),
            changed_fields=list(op.after.keys()),
            changed_by=user_id,
            audit_log_id=audit_log_id,
        ))
    elif op.op_type == "update":
        record = await db.get(model, op.record_id, with_for_update=True)
        before = record.to_dict()
        for k, v in op.after.items():
            setattr(record, k, v)
        record.version += 1
        record.updated_by = user_id
        record.updated_at = now()
        after = record.to_dict()
        db.add(history_model(
            record_id=record.id,
            op_type='update',
            before_snapshot=before,
            after_snapshot=after,
            changed_fields=[k for k in op.after.keys() if before.get(k) != after.get(k)],
            changed_by=user_id,
            audit_log_id=audit_log_id,
        ))
```

---

## 16. AI 运行表

### 16.1 conversations（对话表）

**用途**：记录对话会话（30 分钟无活动自动开新对话）。

```sql
CREATE TABLE conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id),
    started_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    title varchar(200),                 -- AI 自动总结的主题
    summary text,                       -- 长对话的压缩摘要
    message_count int DEFAULT 0
);

CREATE INDEX idx_conversations_user_activity 
    ON conversations(user_id, last_activity_at DESC);
CREATE INDEX idx_conversations_active 
    ON conversations(last_activity_at DESC) WHERE ended_at IS NULL;
```

### 16.2 messages（消息表）

**用途**：对话里的每条消息（用户的、AI 的、工具调用的、工具返回的）。

```sql
CREATE TYPE message_role_enum AS ENUM (
    'user', 'assistant', 'tool_call', 'tool_result', 'system'
);

CREATE TABLE messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES conversations(id),
    role message_role_enum NOT NULL,
    content jsonb NOT NULL,
    tool_name varchar(100),            -- 工具调用时填
    tool_input jsonb,
    tool_output jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
```

### 16.3 pending_issues（待办异常）

**用途**：审计引擎发现的问题，分配给责任人处理。支持自愈（问题消失自动关闭）。

```sql
CREATE TYPE issue_status_enum AS ENUM (
    'open', 'resolved', 'manual_override'
);

CREATE TABLE pending_issues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name varchar(100) NOT NULL,
    issue_key varchar(200) NOT NULL,                -- 去重用的唯一标识
    category varchar(50),
    severity varchar(20) NOT NULL,                  -- low / medium / high
    title varchar(300) NOT NULL,
    description text,
    affected_records jsonb,                         -- 涉及的记录 ID 列表
    owner_user_ids uuid[] NOT NULL,                 -- 分配给谁处理（可多人）
    status issue_status_enum NOT NULL DEFAULT 'open',
    first_detected_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    resolution_method varchar(30),                  -- auto_resolved / manual_override
    detection_count int NOT NULL DEFAULT 1,
    
    CONSTRAINT check_resolved_consistency CHECK (
        (status = 'open') OR 
        (status IN ('resolved', 'manual_override') AND resolved_at IS NOT NULL)
    )
);

-- open 状态的 issue_key 必须唯一（防止重复创建）
CREATE UNIQUE INDEX idx_pending_issues_key_open 
    ON pending_issues(issue_key) WHERE status = 'open';

CREATE INDEX idx_pending_issues_owner ON pending_issues USING gin(owner_user_ids);
CREATE INDEX idx_pending_issues_status_time ON pending_issues(status, last_seen_at DESC);
CREATE INDEX idx_pending_issues_rule ON pending_issues(rule_name, status);
```

**核心自愈逻辑**（审计引擎伪码）：

```python
def run_audit_rule(rule):
    with db.begin():
        violations = rule.check(db)
        detected_keys = set()
        
        for v in violations:
            key = rule.generate_issue_key(v)
            detected_keys.add(key)
            
            existing = db.query(PendingIssue)\
                .filter_by(issue_key=key, status='open').first()
            
            if existing:
                existing.last_seen_at = now()
                existing.detection_count += 1
            else:
                db.add(PendingIssue(...))
        
        # 自愈：之前 open 但这次没发现的 → resolved
        stale = db.query(PendingIssue)\
            .filter_by(rule_name=rule.name, status='open')\
            .filter(PendingIssue.issue_key.notin_(detected_keys))\
            .all()
        for issue in stale:
            issue.status = 'resolved'
            issue.resolved_at = now()
            issue.resolution_method = 'auto_resolved'
```

### 16.4 tool_call_logs（工具调用日志）

**用途**：记录 AI 每次调用工具的详细日志，便于审计和调试。

```sql
CREATE TABLE tool_call_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES conversations(id),
    message_id uuid REFERENCES messages(id),
    user_id uuid REFERENCES users(id),
    tool_name varchar(100) NOT NULL,
    tool_input jsonb,
    tool_output jsonb,
    duration_ms int,
    status varchar(20) NOT NULL,                    -- success / failed
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_tool_calls_conversation ON tool_call_logs(conversation_id);
CREATE INDEX idx_tool_calls_tool ON tool_call_logs(tool_name, created_at DESC);
CREATE INDEX idx_tool_calls_user ON tool_call_logs(user_id, created_at DESC);
```

---

## 17. 配置与辅助表

### 17.1 user_permissions（用户权限表）

```sql
CREATE TABLE user_permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id),
    workflow_name varchar(100) NOT NULL,
    scope_filter jsonb,                    -- 例: {"owner_user_id": "$user_id"}
    allowed boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, workflow_name)
);
```

### 17.2 approval_rules（审批规则表）

```sql
CREATE TABLE approval_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(100) NOT NULL,
    workflow_name varchar(100) NOT NULL,
    match_condition jsonb,                 -- 触发条件（如 amount > 10000）
    approvers jsonb NOT NULL,              -- 审批人列表（角色 + 顺序）
    priority int NOT NULL DEFAULT 0,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_approval_rules_workflow 
    ON approval_rules(workflow_name, priority DESC) 
    WHERE enabled = true;
```

### 17.3 audit_rule_configs（审计规则配置）

```sql
CREATE TABLE audit_rule_configs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name varchar(100) NOT NULL UNIQUE,
    cron_expression varchar(50) NOT NULL,  -- APScheduler 格式
    enabled boolean NOT NULL DEFAULT true,
    config_json jsonb,                     -- 规则特定配置
    last_run_at timestamptz,
    last_run_status varchar(20),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

### 17.4 role_holders（角色持有人）

用于审批流中解析"销售主管"这类角色对应的具体用户。

```sql
CREATE TABLE role_holders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name varchar(50) NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id),
    effective_from date NOT NULL,
    effective_to date,
    is_primary boolean NOT NULL DEFAULT true,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_role_holders_lookup 
    ON role_holders(role_name, effective_from, effective_to);
```

### 17.5 leave_records（请假记录）

用于审批流的自动转移。

```sql
CREATE TABLE leave_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id),
    leave_from date NOT NULL,
    leave_to date NOT NULL,
    delegate_user_id uuid REFERENCES users(id),  -- 委托给谁处理审批
    reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (leave_to >= leave_from)
);

CREATE INDEX idx_leave_records_user 
    ON leave_records(user_id, leave_from, leave_to);
```

---

---

## 完整的 CREATE TABLE 语句（合同表）

```sql
-- 启用 PG 扩展
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enum 类型
CREATE TYPE contract_type_enum AS ENUM (
    'sales', 'purchase', 
    'brokering', 'brokering_sales', 'brokering_purchase',
    'lending_sales', 'lending_purchase'
);

CREATE TYPE contract_status_enum AS ENUM (
    'not_started', 'in_progress', 'completed', 'cancelled'
);

CREATE TYPE subject_company_enum AS ENUM ('subject_a', 'subject_b');

CREATE TYPE contract_role_enum AS ENUM (
    'seller', 'buyer', 'broker_only', 'lender', 'borrower'
);

CREATE TYPE margin_type_enum AS ENUM ('full', 'fixed_ratio', 'fixed_amount');

CREATE TYPE margin_deduction_mode_enum AS ENUM ('proportional', 'at_end');

CREATE TYPE delivery_method_enum AS ENUM ('self_pickup', 'shipped');

-- 合同主表
CREATE TABLE contracts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 标识（注意：contract_number 不在这里加 UNIQUE，而是通过部分唯一索引实现）
    contract_number varchar(50) NOT NULL,
    
    -- 分类
    contract_type contract_type_enum NOT NULL,
    contract_status contract_status_enum NOT NULL DEFAULT 'not_started',
    
    -- 主体与角色
    our_subject_company subject_company_enum,  -- brokering 类型时为 NULL
    our_role contract_role_enum NOT NULL,
    
    -- 交易对手
    party_a_name varchar(200) NOT NULL,
    party_a_company_id uuid REFERENCES companies(id),
    party_b_name varchar(200) NOT NULL,
    party_b_company_id uuid REFERENCES companies(id),
    
    -- 业务员
    salesperson_user_id uuid REFERENCES users(id),
    broker_party_a_user_id uuid REFERENCES users(id),
    broker_party_b_user_id uuid REFERENCES users(id),
    
    -- 商品
    brand_id uuid NOT NULL REFERENCES brands(id),
    product_model varchar(100),
    quantity_tons decimal(12,3) NOT NULL CHECK (quantity_tons > 0),
    unit_price decimal(10,2) CHECK (unit_price IS NULL OR unit_price > 0),
    delivery_location_id uuid NOT NULL REFERENCES delivery_locations(id),
    
    -- 时间
    signed_date date NOT NULL,
    valid_from date NOT NULL,
    valid_to date NOT NULL CHECK (valid_to > valid_from),
    
    -- 保证金
    margin_type margin_type_enum,
    fixed_ratio decimal(5,4) CHECK (fixed_ratio IS NULL OR (fixed_ratio > 0 AND fixed_ratio <= 1)),
    fixed_amount decimal(12,2) CHECK (fixed_amount IS NULL OR fixed_amount > 0),
    margin_deduction_mode margin_deduction_mode_enum,
    
    -- 交付方式
    delivery_method delivery_method_enum,
    freight_per_ton_incl_tax decimal(8,2) CHECK (freight_per_ton_incl_tax IS NULL OR freight_per_ton_incl_tax >= 0),
    find_truck_freight_excl_tax decimal(10,2) CHECK (find_truck_freight_excl_tax IS NULL OR find_truck_freight_excl_tax >= 0),
    
    -- 金额
    total_amount decimal(14,2) NOT NULL CHECK (total_amount >= 0),
    
    -- 撮合佣金
    commission_per_ton_party_a decimal(8,2) CHECK (commission_per_ton_party_a IS NULL OR commission_per_ton_party_a >= 0),
    commission_per_ton_party_b decimal(8,2) CHECK (commission_per_ton_party_b IS NULL OR commission_per_ton_party_b >= 0),
    
    -- 其他
    notes text,
    attachments jsonb,
    
    -- 审计
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_by uuid NOT NULL REFERENCES users(id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version int NOT NULL DEFAULT 1,
    
    -- 软删除
    deleted_at timestamptz,
    deleted_by uuid REFERENCES users(id),
    deleted_reason text,
    
    -- 跨字段约束
    CONSTRAINT check_brokering_no_subject CHECK (
        (contract_type = 'brokering' AND our_subject_company IS NULL) OR
        (contract_type != 'brokering' AND our_subject_company IS NOT NULL)
    ),
    CONSTRAINT check_margin_type_consistency CHECK (
        (margin_type = 'full' AND fixed_ratio IS NULL AND fixed_amount IS NULL 
         AND margin_deduction_mode IS NULL) OR
        (margin_type = 'fixed_ratio' AND fixed_ratio IS NOT NULL AND fixed_amount IS NULL 
         AND margin_deduction_mode IS NOT NULL) OR
        (margin_type = 'fixed_amount' AND fixed_amount IS NOT NULL AND fixed_ratio IS NULL 
         AND margin_deduction_mode IS NOT NULL) OR
        (margin_type IS NULL AND fixed_ratio IS NULL AND fixed_amount IS NULL 
         AND margin_deduction_mode IS NULL)
    ),
    CONSTRAINT check_brokering_commissions CHECK (
        (contract_type LIKE 'brokering%' AND 
         commission_per_ton_party_a IS NOT NULL AND 
         commission_per_ton_party_b IS NOT NULL)
        OR
        (contract_type NOT LIKE 'brokering%' AND 
         commission_per_ton_party_a IS NULL AND 
         commission_per_ton_party_b IS NULL)
    ),
    -- 软删除三字段必须一起赋值或一起为空
    CONSTRAINT check_soft_delete_consistency CHECK (
        (deleted_at IS NULL AND deleted_by IS NULL AND deleted_reason IS NULL) OR
        (deleted_at IS NOT NULL AND deleted_by IS NOT NULL AND deleted_reason IS NOT NULL)
    )
);

-- 索引
CREATE INDEX idx_contracts_type ON contracts(contract_type);
CREATE INDEX idx_contracts_status ON contracts(contract_status);
CREATE INDEX idx_contracts_subject ON contracts(our_subject_company);
CREATE INDEX idx_contracts_salesperson ON contracts(salesperson_user_id);
CREATE INDEX idx_contracts_broker_a ON contracts(broker_party_a_user_id);
CREATE INDEX idx_contracts_broker_b ON contracts(broker_party_b_user_id);
CREATE INDEX idx_contracts_signed_date ON contracts(signed_date DESC);
CREATE INDEX idx_contracts_valid_range ON contracts(valid_from, valid_to);
CREATE INDEX idx_contracts_brand ON contracts(brand_id);
CREATE INDEX idx_contracts_party_a_trgm ON contracts USING gin(party_a_name gin_trgm_ops);
CREATE INDEX idx_contracts_party_b_trgm ON contracts USING gin(party_b_name gin_trgm_ops);
CREATE INDEX idx_contracts_salesperson_status ON contracts(salesperson_user_id, contract_status);

-- 软删除相关
CREATE INDEX idx_contracts_deleted_at ON contracts(deleted_at) WHERE deleted_at IS NOT NULL;
-- 部分唯一索引：合同号在未删除记录间唯一
CREATE UNIQUE INDEX idx_contracts_number_active
    ON contracts(contract_number) WHERE deleted_at IS NULL;

-- PG 权限（阻止物理删除）
-- 应用层角色只有 SELECT, INSERT, UPDATE 权限，没有 DELETE
REVOKE DELETE ON contracts FROM app_user;
```

---

## 设计决策记录（重要）

以下设计决策经过讨论已定稿，Codex 开发时严格遵守：

1. **聚合字段不存储，通过 VIEW 运行时计算**
   - 已提货量、敞口库存、应收应付、总佣金、保证金金额
   - 彻底避免数据不一致
   
2. **甲方乙方保留文本 + 软关联 company_id**
   - 不强制要求每条合同的对方公司都在 companies 表中
   - 支持逐步规范化
   
3. **our_subject_company 只有 subject_a / subject_b 两个值**
   - 撮合主体 C（骋子次方）不入数据
   - brokering 类型合同此字段为 NULL
   - 主体 A 和 B 之间无内部交易
   
4. **借货合同用同一套 schema，语义层面区分**
   - 不独立建表
   - 借货合同只计算保证金 + 额外费用，不计算货款应收应付

5. **合同编号不做格式校验，仅对未删除记录强制唯一**
   - 部分唯一索引 `WHERE deleted_at IS NULL`
   - 由业务员自行维护编号规则
   
6. **应收应付通过 VIEW 计算，不存字段**
   - 四种分支：借货 / 全款 / 按比例扣除 / 最后扣除
   - 每次查询都是最新值
   - 撮合纯中介不计算应收应付（只计算佣金）

7. **严禁物理删除，全局软删除机制**
   - 所有业务表带 `deleted_at / deleted_by / deleted_reason`
   - 区分"作废"（contract_status=cancelled）vs "删除"（deleted_at 有值）
   - 主数据表用 `is_active`
   
8. **状态流转受约束**
   - 软删除后禁止更新（除恢复操作）
   - 恢复前检查号码冲突

9. **工单-调度-委托的关联方向**
   - 工单表不存调度列表
   - 调度表持有 `delivery_order_id` 和 `delegation_id`
   - 委托表持有 `source_order_id`

10. **调度拆分规则：三维度任一不同都拆分**（v0.5 新增）
    - 拆分维度：提货地 / 品牌 / 型号
    - 任一维度不同 → 新建独立调度记录
    - 编号规则：`DD-YYYYMMDD-NNN-A/-B/-C`
    - 调度的品牌/型号/提货地是**实际物流记录**，可与合同约定不同

11. **价格模型锁定：合同单价是真源**（v0.5 新增）
    - 合同的 quantity_tons 和 unit_price 是价格体系的真源
    - 工单/委托的 unit_price 必须等于对应合同的 unit_price
    - 业务员创建工单/委托时 unit_price 自动拷贝，不允许手改
    - 改价必须通过"修改合同"workflow，不允许在工单/委托绕过
    - 品牌/型号/提货地的灵活调整不影响价格
    - 额外费用通过 `extra_fee` / `extra_payment` 字段记录，独立于单价

12. **流水表只读 + 汇总对账模式**（v0.6 新增）
    - transactions 只有 `import_transactions` workflow 能写
    - 原始字段（流水号/时间/主体/对方/方向/金额）一旦写入永久不变（TRIGGER 保护）
    - PG REVOKE DELETE 权限阻止物理删除
    - 不在流水表关联合同（不存 contract_id / purpose 字段）
    - 对账通过 `v_reconciliation` 视图实现：按 (主体 × 对方公司) 汇总
    - 公司名规范化靠 company_aliases 映射

13. **审计表只允许 INSERT + SELECT**（v0.6 新增）
    - audit_logs、所有 history 表在 PG 层 REVOKE UPDATE/DELETE
    - 历史快照永不修改
    - 软删除自身也要写 history（op_type='soft_delete'）

14. **对话和待办数据保留策略**（v0.6 新增）
    - conversations / messages 永久保留（至少 2 年内）
    - pending_issues 自愈机制（问题消失自动 resolved）
    - tool_call_logs 保留 90 天（Phase 2 定期归档）

---

## 首次建库清单（给 Codex 的第 1 周任务参考）

以下表必须在第 1 周一次性建好（一次 Alembic migration）：

**业务表 + history 表（10 张）**:
- contracts + contracts_history
- delivery_orders + delivery_orders_history
- delivery_delegations + delivery_delegations_history
- dispatches + dispatches_history
- transactions + transactions_history

**主数据表（5 张）**:
- users
- companies
- brands
- products
- delivery_locations

**别名表（3 张）**:
- company_aliases
- brand_aliases
- product_aliases

**审计三件套（3 张）**:
- audit_logs
- change_proposals
- approval_records

**AI 运行表（4 张）**:
- conversations
- messages
- pending_issues
- tool_call_logs

**配置表（5 张）**:
- user_permissions
- approval_rules
- audit_rule_configs
- role_holders
- leave_records

**视图（5 个）**:
- v_contracts_with_aggregates
- v_transactions_normalized
- v_transaction_balance_by_counterparty
- v_contract_balance_by_counterparty
- v_reconciliation

**TRIGGER / 权限 / 扩展**:
- 扩展：pg_trgm
- TRIGGER：transactions 表的原始字段保护
- 权限：app_user 角色 REVOKE DELETE ON transactions
- 权限：app_user 角色 REVOKE UPDATE, DELETE ON audit_logs
- 权限：app_user 角色 REVOKE UPDATE, DELETE ON 所有 history 表

**合计约 30 张表 + 5 个视图，一次建好**。后续 Phase 2 再加表时做增量 migration。

---

## 附录 A：公司简称自动生成规则（v1.0）

本附录定义 `generate_aliases(formal_name: str) -> list[str]` 函数的完整规则。此函数实现在 `app/services/alias_generator.py`，**同时被**以下场景调用：

1. **W1 批量导入**：`scripts/import_companies.py` 把 1712 家历史客户一次性生成简称
2. **`create_company` workflow**：新增公司时自动生成建议简称
3. **Phase 2 重算任务**：算法升级后可按 `generator_version` 批量重新生成

### A.1 生成策略（3 层剥离）

输入全名 `formal_name`，输出简称列表（通常 2-3 个）。

**Step 0：去括号**

```
"涂多多（青岛）跨境电子商务有限公司" → "涂多多跨境电子商务有限公司"
```

用正则 `[（(][^）)]*[）)]` 剔除所有全/半角括号及其内容。

**Step 1：剥除公司性质后缀**

按最长匹配，反复剥除以下后缀（最多 3 轮）：

```python
SUFFIXES = [
    "股份有限公司", "有限责任公司", "有限公司", "股份公司",
    "集团有限公司", "集团公司", "集团",
    "合伙企业", "普通合伙", "有限合伙",
    "个人独资企业", "个体工商户",
    "分公司", "办事处",
]
```

得到"核心名"：
```
"涂多多跨境电子商务有限公司" → "涂多多跨境电子商务"
"张家港辉凡新材料科技有限公司" → "张家港辉凡新材料科技"
```

**Step 2：剥离地理前缀**

识别省级+地级市前缀，得到"无地理核心名"和"地理前缀"。支持形式：
- `浙江XX` / `浙江省XX`
- `张家港XX` / `张家港市XX`
- `浙江义乌XX` / `浙江省义乌市XX`

完整词典见 `app/services/alias_generator.py`（包含 31 省 + 约 200 地级市）。

```
"张家港辉凡新材料科技" → 核心名="辉凡新材料科技"，地理前缀="张家港"
```

**Step 3：反复剥除业务类型后缀**

按最长匹配，反复剥除以下后缀（最多 3 轮，但不剥到 <2 字）：

```python
BUSINESS_SUFFIXES = [
    "科技", "实业", "贸易", "商贸", "工贸", "发展",
    "塑业", "塑胶", "塑化", "新材料", "材料", "化工",
    "包装", "制品", "饰品", "玩具", "食品", "饮品",
    "橡塑", "印务", "印刷", "建材",
    "进出口", "国际贸易", "国际",
    "投资", "企业管理", "管理",
]
```

得到两个版本：
- `shortest`：反复剥除后的最短核心（如"辉凡"）
- `mid`：只剥一次后的中间形态（如"辉凡新材料"）

### A.2 生成候选简称

从上述产物组合生成候选，去重后返回：

| 候选名 | 例子（对 "张家港辉凡新材料科技有限公司"）|
|-------|----------------------------------------|
| `shortest` | 辉凡 |
| `mid`（若与 shortest 不同）| 辉凡新材料 |
| 地理前缀 + shortest | 张家港辉凡 |

### A.3 过滤规则

以下情况不产出简称：
- 简称长度 < 2 字
- 简称 == formal_name
- 简称 == 去括号后的全名（避免只剥括号的无效简称）

### A.4 异常检测

以下情况标记为"异常"，不生成简称并记录到人工 review 清单：
- 全名为空
- 剥除公司性质后缀后核心 ≤ 3 字（可能是个人名或不规范录入）
- `XX厂`、`XX百货店`、`XX商行` 等非公司实体（词典外的后缀暂不覆盖，会不生成简称）

### A.5 冲突检测

生成后检测：同一个简称被**多家公司**指向。这些冲突**不需要阻止**，由运行期 AI 反问处理。但要记录到 `conflicts.xlsx` 供人工 review（例如"国贸"对应多家，可能需要业务员人工删除某些误生成的）。

### A.6 算法版本化

`generator_version` 字段跟踪用的是哪一版规则生成的。当前版本 `v1.0`。

升级规则时步骤：
1. 在 `alias_generator.py` 新增 `generate_aliases_v2()`，`version="v1.1"`
2. 测试验证新规则输出更好
3. 运行定时任务 `rebuild_aliases`：把 `source='auto_generated' AND generator_version < 'v1.1'` 的简称全部软删除，重新生成
4. 业务员手工维护的（source=manual/disambiguation）**不动**

### A.7 实测数据（v1.0 在 1712 家公司上）

| 指标 | 数值 |
|------|------|
| 公司总数 | 1712 |
| 成功生成简称 | 1667（97.4%）|
| 简称总数 | 约 3500 |
| 平均每公司简称数 | 2.0 |
| 简称冲突组 | 51 组（需 AI 反问处理）|
| 疑似重复公司组 | 22 组（待人工合并）|

详细统计见 `/docs/aliases-review.md`。

---

*v0.9 - 2026-04-21 brand_aliases / product_aliases 完整设计 + AI 简称查询逻辑（46 + 77 条简称）*
*v0.8 - 2026-04-21 品牌/型号/提货地按真实主数据重构 + 提货地变为品牌专属*
*v0.7 - 2026-04-21 companies 表工商信息扩展 + company_aliases 支持版本化 + 自动生成规则附录*
*v0.6 - 2026-04-20 全表完整，可交付 Codex 第 1 周建库*
*v0.5 - 2026-04-20 价格模型锁定 + 调度拆分规则*
*v0.4 - 2026-04-20 新增应收应付 + 提货链表*
*v0.3 - 2026-04-20 新增软删除机制*
*v0.2 - 2026-04-20 基于真实数据 + 业务访谈*

---

## 附录 B：主数据导入流程（W1 必做）

### B.1 输入文件

W1 任务 1.3 在 `data-import/` 目录下应有：

| 文件 | 行数 | 关联键 |
|------|------|-------|
| brands_master.xlsx | 34 | (无外部关联) |
| products_master.xlsx | 45 | brand_name → brands.formal_name |
| delivery_locations_master.xlsx | 55 | brand_name → brands.formal_name |
| brand_aliases_final.xlsx | 46 | brand_name → brands.formal_name（已 review）|
| product_aliases_master.xlsx | 77 | (brand_name, model_code) → products |
| companies_final.xlsx | 1679 | (无外部关联) |
| aliases_final.xlsx | 3432 | formal_name → companies.formal_name |

### B.2 导入顺序与脚本

必须按以下顺序导入（外键依赖）：

```
1. import_brands.py             → brands 表 (34 条)
2. import_products.py           → products 表 (45 条, 用 brand_name 反查 brand_id)
3. import_delivery_locations.py → delivery_locations 表 (55 条, 同上)
4. import_brand_aliases.py      → brand_aliases 表 (46 条, 已 review)
5. import_product_aliases.py    → product_aliases 表 (77 条, 用 (brand_name, model_code) 反查 product_id)
6. import_companies.py          → companies 表 (1679 条) + 同时导入 company_aliases
```

### B.3 关键实现点

**关于 uuid 生成**：

```python
# import_brands.py 简化伪码
brand_name_to_uuid: dict[str, UUID] = {}

for row in xlsx_rows:
    new_uuid = uuid4()
    INSERT INTO brands (id=new_uuid, formal_name=row.formal_name, ...)
    brand_name_to_uuid[row.formal_name] = new_uuid

# 把 mapping 持久化到一个临时文件,供后续 import 脚本用
save_pickle("brand_name_to_uuid.pkl", brand_name_to_uuid)
```

```python
# import_products.py 简化伪码
brand_name_to_uuid = load_pickle("brand_name_to_uuid.pkl")

for row in xlsx_rows:
    brand_uuid = brand_name_to_uuid.get(row.brand_name)
    if not brand_uuid:
        # 严重错误: brands_master.xlsx 里没有这个品牌
        raise ImportError(f"品牌 '{row.brand_name}' 不存在,请先在 brands_master.xlsx 中添加")
    INSERT INTO products (id=uuid4(), brand_id=brand_uuid, model_code=row.model_code, ...)
```

**容错原则**：
- 导入脚本必须**事务化**：5 步导入要么全成功要么全回滚
- 每步前先 SELECT COUNT(*) 检查目标表是否为空（防止重复导入）
- 如果发现主数据不一致（如 products xlsx 里出现 brands xlsx 没有的品牌名），**报错停止，不允许悄悄创建**

### B.4 导入完成后的验证

```sql
-- brands 应有 34 条
SELECT COUNT(*) FROM brands;

-- products 应有 45 条,且每条都能 JOIN 到 brand
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM products p JOIN brands b ON b.id = p.brand_id;
-- 两条 SQL 数字必须一致

-- delivery_locations 同理
SELECT COUNT(*) FROM delivery_locations;
SELECT COUNT(*) FROM delivery_locations l JOIN brands b ON b.id = l.brand_id;

-- companies 1679 条
SELECT COUNT(*) FROM companies;

-- company_aliases 3432 条
SELECT COUNT(*) FROM company_aliases;
```

---

## 附录 C：历史合同导入的品牌名映射

见 5b 章。导入历史 250 条合同时由 `scripts/import_historical_contracts.py` 处理。

