# workflows.md - Workflow 定义文档

> **版本**: v0.1（第一版，10 个核心 workflow）
> **状态**: 结构完整，细节可在开发时迭代
> **配套文档**: schema.md v0.6、01-project-blueprint.md、02-development-plan.md

---

## 关于此文档

本文档定义系统中所有业务 Workflow 的详细规格。

### Workflow 是什么

Workflow 是**完整的业务动作**，不是原子数据库操作。一个 Workflow 封装了：
- 参数校验
- 权限检查
- 关联数据查询
- 业务规则校验
- 生成操作方案（Plan）
- 事务执行
- 事后核验

业务员的一次操作意图对应一个 workflow。每个 workflow 执行完是**原子的业务行为**。

### Workflow 的执行流程

```
业务员自然语言输入
  ↓
AI 理解意图 + 澄清参数
  ↓
workflow.plan(params) → 生成 Plan
  ├── 校验参数
  ├── 查询关联数据
  ├── 生成 operations（insert/update/delete 列表）
  ├── 跑规则校验
  └── 标记所需审批
  ↓
飞书卡片展示 Plan 预览
  ↓
用户确认
  ↓
（如需审批）审批人决策
  ↓
ProposalExecutor.execute(plan)
  ├── 事务开始
  ├── 重跑规则校验
  ├── 执行每个 operation（同事务写 history）
  ├── 事后核验
  └── 事务提交
  ↓
飞书卡片回显结果
```

### 10 个核心 Workflow 清单

| # | Workflow 名 | 用途 | 估复杂度 | 开发周次 |
|---|------------|------|---------|---------|
| 1 | create_sales_contract | 新建销售合同 | 中 | W3 |
| 2 | create_purchase_contract | 新建采购合同 | 中 | W8 |
| 3 | create_brokering_contract | 新建撮合合同 | 中 | W8 |
| 4 | update_contract_quantity | 修改合同数量 | 高 | W3 |
| 5 | update_contract_price | 修改合同单价 | 高 | W8 |
| 6 | cancel_contract | 作废合同 | 中 | W8 |
| 7 | soft_delete_contract | 逻辑删除合同 | 中 | W8 |
| 8 | create_delivery_order | 新建提货工单 | 中 | W9 |
| 9 | create_delivery_delegation | 新建提货委托 | 中 | W9 |
| 10 | create_dispatch | 新建车辆调度（含拆分） | 中 | W9 |

### Phase 2 待做的 Workflow

- `import_transactions` - 流水导入（必须做，可排进 Phase 1.5）
- `restore_deleted_contract` - 恢复误删
- `split_executed_contract` - 拆分已执行合同（最复杂）
- `update_delivery_order` / `cancel_delivery_order`
- `update_dispatch` / `cancel_dispatch`
- `auto_reconcile_transactions` - 自动对账

---

## Workflow 定义标准格式

每个 Workflow 按以下结构描述：

```
## N. <workflow_name>（中文名）

### 用途
一句话说明业务意图。

### 触发场景
业务员可能的自然语言表达（至少 3 个示例）。

### 输入参数
必填字段 + 可选字段 + 系统自动填的字段。

### 前置条件
不满足就拒绝，不进入 Plan 生成。

### 业务规则校验
Plan 生成时要跑的规则（error 阻塞，warning 不阻塞）。

### 操作序列
具体的 operation 列表（INSERT/UPDATE/DELETE 哪些表）。

### 异常分支
遇到特殊情况怎么办（可能需要暂停问用户）。

### 审批要求
是否需要审批、几级、什么条件下需要。

### 事后核验
执行完后要验证什么，失败则整体回滚。

### 自然语言回复模板
AI 生成的 Plan 预览文本范例。
```

---

## 1. create_sales_contract（新建销售合同）

### 用途
业务员创建一份新的销售合同，我方（主体 A 或 B）作为甲方（销售方）向外部客户销售货物。

### 触发场景
- "帮我新建一份销售合同，卖给美远，三房 302，330 吨，8000 一吨"
- "给张家港赫烽建个采购合同 100 吨，水料"
- "客户要下单，瞿谊主体，CZ-318，165 吨，6200"

### 输入参数

**业务员必须提供**:
| 参数 | 类型 | 说明 |
|-----|------|------|
| our_subject_company | enum | `subject_a` 或 `subject_b`（我方主体）|
| customer_name | string | 客户名称（对方乙方）|
| brand_name | string | 品牌（需模糊匹配，支持简称）|
| product_model | string | 型号（可选，水料类可空）|
| quantity_tons | number | 数量（吨），> 0 |
| unit_price | number | 单价（元/吨），> 0 |
| delivery_location | string | 提货地（需模糊匹配）|
| valid_from | date | 合同开始日期 |
| valid_to | date | 合同结束日期 |
| margin_type | enum | `full` / `fixed_ratio` / `fixed_amount` |
| fixed_ratio | number | 固定比例（margin_type=fixed_ratio 时必填，如 0.1）|
| fixed_amount | number | 固定金额（margin_type=fixed_amount 时必填）|
| margin_deduction_mode | enum | `proportional` / `at_end`（margin_type 非 full 时必填）|
| delivery_method | enum | `self_pickup` / `shipped` |

**业务员可选提供**:
| 参数 | 类型 | 说明 |
|-----|------|------|
| contract_number | string | 合同编号（空则系统生成 `SALES-YYYYMMDD-NNN`）|
| signed_date | date | 签订日期，默认今天 |
| freight_per_ton_incl_tax | number | 含税运费（元/吨），shipped 时常填 |
| find_truck_freight_excl_tax | number | 帮找车运费（元/车），可选 |
| notes | text | 备注 |
| commission_per_ton_party_a | number | 撮合甲方佣金（仅撮合销售填）|
| commission_per_ton_party_b | number | 撮合乙方佣金（仅撮合销售填）|

**系统自动填**:
- contract_type = `sales`（普通销售）或 `brokering_sales`（撮合销售）或 `lending_sales`（借货销售）
- our_role = `seller` 或 `lender`
- party_a_name = 根据 our_subject_company 推导（"安徽趋易贸易有限公司" 或 "上海瞿谊实业有限公司"）
- party_b_name = customer_name
- contract_status = `not_started`
- total_amount = quantity_tons × unit_price
- salesperson_user_id = 当前登录用户（若有 sales 角色）
- created_by / updated_by = 当前用户
- version = 1

### 前置条件

1. 业务员有 `create_sales_contract` 权限
2. 品牌通过模糊匹配能唯一确定（多候选需先澄清）
3. 提货地通过模糊匹配能唯一确定
4. 合同编号（如果手动提供）当前未被占用（未删除记录中）

### 业务规则校验

**硬规则（error，阻塞）**:
- `quantity_tons > 0`
- `unit_price > 0`
- `valid_to > valid_from`
- margin_type = fixed_ratio 时 `0 < fixed_ratio ≤ 1`
- margin_type = fixed_amount 时 `fixed_amount > 0`
- margin_type = full 时 `fixed_ratio` 和 `fixed_amount` 必为空
- our_subject_company 不能为空（销售合同必有我方主体）
- 合同号（如手动提供）格式合法（非空、长度 ≤ 50）

**软规则（warning，不阻塞但提醒）**:
- `signed_date > valid_from`（倒签合同，需确认）
- `total_amount > 100 万`（大额合同，触发审批提醒）
- `unit_price` 偏离该客户/品牌过去 30 天均价 > 10%（价格异常，请确认）

### 操作序列

1. **推导派生字段**:
   - 根据 our_subject_company 查询对应公司全名 → 填 party_a_name
   - 根据 brand_name 模糊匹配 → brand_id
   - 根据 delivery_location 模糊匹配 → delivery_location_id
   - 计算 total_amount = quantity_tons × unit_price
   - 若 contract_number 为空，生成 `SALES-YYYYMMDD-NNN`（NNN 为当日自增）
   
2. **INSERT contracts**（1 条记录）
   
3. **INSERT contracts_history**（op_type='insert'，before=null，after=完整行）

### 异常分支

**场景 A：合同号冲突**
- 系统检测到 contract_number 已存在（未删除记录中）
- 暂停，询问业务员：重新输入 / 让系统生成新号 / 取消

**场景 B：品牌模糊匹配多候选**
- "三房" 匹配到"三房巷"和"三房牌"
- 暂停，让业务员选一个

**场景 C：客户公司未在 companies 表**
- 允许创建（文本字段），但提示"这个客户我们第一次合作？要不要加到客户主数据？"
- 不强制要求立即加

**场景 D：价格异常**
- 单价偏离历史价格 > 10%
- 给警告但不阻塞，业务员确认即可继续

### 审批要求

**默认规则**（可在 approval_rules 表配置）:
- `total_amount ≤ 50 万`：无需审批
- `50 万 < total_amount ≤ 200 万`：一级审批（部门主管）
- `total_amount > 200 万`：二级审批（部门主管 + 老板）

### 事后核验

- 查询刚 INSERT 的合同，确认所有字段正确填入
- 确认 `total_amount == quantity_tons × unit_price`（误差 < 0.01）
- 确认 contracts_history 有对应记录
- 确认 audit_log 有对应记录

核验失败 → 整体事务回滚，状态改为 failed。

### 自然语言回复模板

```
我将要创建一份新合同：

📋 销售合同（未执行）
• 编号：SALES-20260420-003（自动生成）
• 甲方：上海瞿谊实业有限公司
• 乙方：美远贸易有限公司
• 商品：三房巷 CZ-302，330 吨 × 8000 元 = 264 万元
• 提货地：江阴
• 合同期：2026-04-20 至 2026-06-30
• 保证金：10% 固定比例（26.4 万），按比例扣除
• 负责业务员：李成子

⚠️ 需要一级审批（部门主管），因为金额 > 50 万

确认创建吗？[确认] [取消]
```

---

## 2. create_purchase_contract（新建采购合同）

### 用途
创建一份采购合同，我方（主体 A 或 B）作为乙方（采购方）从外部供应商采购货物。

### 触发场景
- "从张家港辉凡买一批三房 302，100 吨，6600"
- "录入一个采购合同，浙江塑界，瞿谊主体"

### 输入参数

与 create_sales_contract 对称，核心区别：
- supplier_name（供应商）替代 customer_name
- contract_type = `purchase` / `brokering_purchase` / `lending_purchase`
- our_role = `buyer` / `borrower`
- party_a_name = supplier_name（外部供应商）
- party_b_name = 根据 our_subject_company 推导（我方）

### 前置条件 / 业务规则 / 异常分支 / 审批要求

与 create_sales_contract 结构相同，区别在于：
- 审批阈值可以不同（采购金额阈值通常比销售低）
- 价格合理性检查：对比该品牌过去的采购均价

### 事后核验 / 回复模板

同销售合同结构。

---

## 3. create_brokering_contract（新建撮合合同）

### 用途
创建一份纯撮合合同，我方不作为交易主体，只赚取佣金。甲方和乙方都是外部公司。

### 触发场景
- "记录一笔撮合，甲方张家港辉凡，乙方台州绿鼎红，300 吨，佣金每吨 20"
- "黄佳欣促成的单子，撮合合同"

### 输入参数

**必填**:
| 参数 | 说明 |
|-----|------|
| party_a_name | 甲方（销售方，外部）|
| party_b_name | 乙方（采购方，外部）|
| brand_name, product_model, quantity_tons, unit_price | 同上 |
| delivery_location, valid_from, valid_to | 同上 |
| broker_party_a_user_id | 撮合甲方业务员 |
| broker_party_b_user_id | 撮合乙方业务员 |
| commission_per_ton_party_a | 甲方佣金单价（元/吨），可为 0 |
| commission_per_ton_party_b | 乙方佣金单价（元/吨），可为 0 |

**系统自动填**:
- contract_type = `brokering`
- our_role = `broker_only`
- **our_subject_company = NULL**（撮合我方不是交易主体）
- salesperson_user_id = NULL（撮合不要主业务员）
- margin_type / margin_deduction_mode = NULL（撮合不涉及保证金）

### 特殊前置条件

- party_a_name 和 party_b_name 都**不能**包含"安徽趋易"或"上海瞿谊"（撮合合同我方不作为主体）
- broker_party_a_user_id 和 broker_party_b_user_id 必填（两边业务员都要记录）
- 至少一方佣金 > 0（否则没有业务意义）

### 业务规则

- 不计算保证金金额
- 不计算应收应付（应视图中 receivable_amount / payable_amount 都是 NULL）
- 只计算佣金（total_commission_party_a / total_commission_party_b）

### 审批要求

- 撮合合同一般不走审批（我方不担风险）
- 但高佣金单（> 10 万）可考虑一级审批

---

## 4. update_contract_quantity（修改合同数量）

### 用途
修改已存在合同的数量。这是一个**高风险**操作——因为涉及提货量守恒、应收应付重算。

### 触发场景
- "把 C20260312 改成 200 吨"
- "美远的那个合同，数量改成 100"
- "L20260315 实际少提了 10 吨，调整一下数量"

### 输入参数

**必填**:
- contract_id（或 contract_number，AI 先解析为 id）
- new_quantity_tons（新数量）
- reason（修改原因，必填）

### 前置条件

1. 业务员有 `update_contract_quantity` 权限
2. 合同存在且未软删除
3. 合同状态为 `not_started` 或 `in_progress`（不能改已完结或已作废）
4. 业务员是合同负责人或管理员

### 业务规则校验

**硬规则（error）**:
- new_quantity_tons > 0
- **new_quantity_tons ≥ 已提货量**（销售侧 + 采购侧，不允许改到低于实际提货的值）

**软规则（warning）**:
- 变化幅度 > 50% → 警告
- 合同执行进度 > 80% 还要改数量 → 警告

### 操作序列

1. **查询当前合同**（含关联提货统计）
2. **生成 UPDATE operation**:
   - 更新 quantity_tons
   - 重新计算 total_amount（= new_quantity × 原单价）
   - 如果 margin_type = full，margin_amount 也会隐式变化（视图重算）
   - 如果 margin_type = fixed_ratio，margin_amount 也会隐式变化
   - 更新 version、updated_by、updated_at
3. **INSERT contracts_history**（op_type='update'）

### 异常分支

**场景 A：新数量低于已提货量**
- 硬错误，直接拒绝，提示业务员当前已提 X 吨，新数量不能低于此

**场景 B：合同已完结**
- 拒绝，提示需要走"拆分已执行合同"workflow（Phase 2）

**场景 C：合同当前有 pending 的 workflow**
- 拒绝，提示先处理 pending 的那个

### 审批要求

- 变化幅度 ≤ 10%：无需审批
- 10% < 变化幅度 ≤ 30%：一级审批（部门主管）
- 变化幅度 > 30%：二级审批（部门主管 + 老板）

### 事后核验

- 查询修改后合同，确认 quantity_tons 已更新
- 确认 total_amount 已同步（quantity × unit_price）
- 确认 history 有对应记录
- **确认 v_contracts_with_aggregates 视图中的 receivable_amount 已重新计算**（验证视图正常工作）

### 自然语言回复模板

```
操作预览 — 修改合同数量

📋 合同 C20260312（美远贸易，三房 302）
• 数量：330 吨 → 200 吨（减少 130 吨）
• 总金额：264 万 → 160 万
• 已提货：135 吨（< 200 吨 ✓ 合法）
• 修改原因：客户要求减量

⚠️ 变化幅度 39.4%，需要二级审批

确认修改吗？[确认] [取消]
```

---

## 5. update_contract_price（修改合同单价）

### 用途
修改合同单价。注意：**会影响所有关联工单和委托的单价**（因为工单/委托单价必须等于合同单价）。

### 触发场景
- "C20260312 的单价改成 8200"
- "美远合同涨价 200 块"

### 输入参数

- contract_id
- new_unit_price
- reason

### 业务规则校验

- new_unit_price > 0
- 变化幅度 > 15% → 硬警告（不阻塞但需要显式确认）

### 操作序列

1. **查询当前合同和关联工单/委托**
2. **生成 UPDATE operations**:
   - UPDATE contracts SET unit_price = new_unit_price（total_amount 随之变化）
   - UPDATE delivery_orders（关联 orders）SET unit_price = new_unit_price（级联更新）
   - UPDATE delivery_delegations（关联 delegations）SET unit_price = new_unit_price
3. **为每个表 INSERT history 记录**

### 异常分支

**场景 A：已有完成的工单**
- 如果工单对应的流水已经进账了，改单价会造成账面混乱
- 拒绝，提示只能对未开始/执行中的合同改价

### 审批要求

- 必须二级审批（因为级联影响大）

### 事后核验

- 确认所有关联工单和委托的 unit_price 已同步
- 确认 total_amount 全部重算

---

## 6. cancel_contract（作废合同）

### 用途
**业务意义上的作废**：合同因商业原因终止（客户违约、双方协商终止、货源出问题）。数据保留在系统中，状态变为 `cancelled`，但不从查询视图中消失。

### 触发场景
- "这个合同作废吧，客户跑路了"
- "C20260312 客户违约，作废处理"

### 输入参数

- contract_id
- cancel_reason（必填，作废原因）

### 前置条件

1. 合同状态必须是 `not_started` 或 `in_progress`
2. 业务员有权限（合同负责人或管理员）

### 业务规则

- 作废已有提货的合同要特别警告（`已提货量 > 0`）
- 提示业务员考虑是否需要：
  - 一并作废关联的未完成工单（通过 cascade 选项）
  - 退还已收保证金（需手动处理流水）

### 操作序列

1. UPDATE contracts SET contract_status = 'cancelled', notes 追加作废信息
2. INSERT contracts_history

### 异常分支

**场景 A：合同有关联的活跃工单/委托**
- 暂停，询问业务员：
  - 选项 1：一并作废所有关联工单/委托
  - 选项 2：保持工单/委托不变，只作废合同（不推荐，会产生孤儿数据）
  - 选项 3：取消作废操作
- 根据选择生成多个 UPDATE operations

### 审批要求

- 默认一级审批（部门主管）
- 大额合同（> 100 万）二级审批

---

## 7. soft_delete_contract（逻辑删除合同）

### 用途
**数据意义上的删除**：录错了、重复了、测试数据。合同数据保留在数据库但不出现在正常查询视图中。

### 触发场景
- "刚才那个合同录错了，删掉"
- "C20260312 是重复的，删除"

### 输入参数

- contract_id
- delete_reason（必填，删除原因）

### 前置条件

1. 业务员有删除权限（权限较严格）
2. 合同没有关联的活跃提货工单/委托（有则需先处理）

### 操作序列

1. UPDATE contracts SET deleted_at = now(), deleted_by = 当前用户, deleted_reason
2. INSERT contracts_history（op_type='soft_delete'）

### 异常分支

**场景 A：合同有关联的非删除状态的工单/委托**
- 拒绝（默认）或暂停询问：
  - 选项 1：一并软删除所有关联
  - 选项 2：先取消/软删除关联后再来

### 审批要求

**比作废更严格**：
- 必须二级审批
- 执行时主动发通知到老板

---

## 8. create_delivery_order（新建提货工单）

### 用途
基于销售合同新建一次提货工单，记录客户发起的一次提货请求。

### 触发场景
- "美远要提 33 吨，建个工单"
- "C20260312 提货，100 吨"

### 输入参数

**必填**:
| 参数 | 说明 |
|-----|------|
| sales_contract_id | 销售合同 ID |
| quantity_tons | 本次提货数量（吨）|

**可选**:
| 参数 | 说明 |
|-----|------|
| extra_fee | 额外费用（元）|
| extra_fee_notes | 额外费用说明 |
| notes | 备注 |

**系统自动填**:
- order_number：生成 `THGD-YYYYMMDD-NNNN`
- status = `normal`
- **unit_price = 对应销售合同的 unit_price**（强制拷贝，不允许手改）
- customer_name_snapshot = 合同的 party_b_name
- our_subject_snapshot = 合同的 our_subject_company 对应的公司名
- created_by = 当前用户

### 前置条件

1. 销售合同存在、未删除、状态为 not_started 或 in_progress
2. 业务员有权限

### 业务规则校验

**硬规则（error）**:
- `quantity_tons > 0`
- **工单累计后不超过合同数量**:
  ```
  SUM(active_orders.quantity_tons) + new_quantity ≤ contract.quantity_tons
  ```

### 操作序列

1. 查询合同和已有工单（算出剩余可提量）
2. 生成工单号
3. INSERT delivery_orders
4. INSERT delivery_orders_history
5. **如果合同状态是 `not_started`，更新为 `in_progress`**（首次提货的状态流转）

### 异常分支

**场景 A：超过合同剩余量**
- 硬拒绝，提示剩余可提 X 吨，当前想提 Y 吨

**场景 B：合同即将到期（< 7 天）**
- 警告但不阻塞

### 审批要求

- 默认无需审批（提货是日常操作）
- 大额工单（> 50 万）可配置一级审批

### 事后核验

- 确认 unit_price 等于合同单价（防止被改）
- 确认合同状态正确流转
- 确认 history 记录

---

## 9. create_delivery_delegation（新建提货委托）

### 用途
基于采购合同新建提货委托，关联到来源工单。一个工单可能对应多条委托（因为同一次提货可能来自不同采购合同）。

### 触发场景
- "给刚才那个工单建委托，从张家港辉凡的合同走，33 吨"
- "工单 THGD-20260405-001 对应的委托建一下"

### 输入参数

**必填**:
| 参数 | 说明 |
|-----|------|
| source_order_id | 来源工单 ID |
| purchase_contract_id | 采购合同 ID |
| quantity_tons | 委托数量（吨）|

**可选**:
| 参数 | 说明 |
|-----|------|
| extra_payment | 额外支付金额（元）|
| extra_payment_notes | 额外支付说明 |

**系统自动填**:
- delegation_number：生成 `THWT-YYYYMMDD-NNNN`
- status = `normal`
- **unit_price = 采购合同的 unit_price**（强制）
- supplier_name_snapshot = 采购合同的 party_a_name
- our_subject_snapshot = 主体名
- created_by = 当前用户

### 前置条件

1. 来源工单存在且未删除
2. 采购合同存在且未删除，状态为 not_started / in_progress
3. **采购合同的 our_subject_company 必须等于工单对应销售合同的 our_subject_company**（主体一致性）
4. **采购合同的品牌/型号建议等于销售合同**（不强制，但有偏离时提醒）

### 业务规则校验

**硬规则**:
- `quantity_tons > 0`
- 采购合同剩余可提量 ≥ quantity_tons
- 同一工单下所有委托数量之和 ≤ 工单数量

**软规则**:
- 采购合同品牌 ≠ 销售合同品牌 → 警告（业务允许，但提醒业务员）
- 委托数量 < 工单剩余数量（意味着还要开其他委托）→ 提示剩余多少待补

### 操作序列

1. 查询工单和采购合同的剩余量
2. 生成委托号
3. INSERT delivery_delegations
4. INSERT delivery_delegations_history
5. 如果采购合同状态 `not_started`，更新为 `in_progress`

### 异常分支

**场景 A：工单还有剩余未分配**
- 允许创建部分委托
- 提示业务员还需 X 吨补委托

**场景 B：主体不一致**
- 销售合同是主体 A 的，采购合同是主体 B 的 → 硬拒绝（主体 A/B 不做内部交易）

### 审批要求
- 默认无需审批

---

## 10. create_dispatch（新建车辆调度）

### 用途
记录一车实际发车的详细信息。**含拆分判断逻辑**：如果工单需要按提货地/品牌/型号拆分，业务员需逐条创建调度。

### 触发场景
- "工单 THGD-001 安排一车，司机刘全，皖B12971，33 吨"
- "给这个工单分 3 车，都是三房 302，江阴"
- "一车装两种型号，22 吨 302，11 吨 328"

### 输入参数

**必填**:
| 参数 | 说明 |
|-----|------|
| delivery_order_id | 关联工单 ID |
| dispatch_mode | `driver`（个人司机）或 `logistics`（物流公司）|
| load_tons | 本车装载量（吨）|
| delivery_date | 提货日期 |
| brand_id | **实际提货品牌** |
| product_model | **实际提货型号** |
| delivery_location_id | **实际提货地** |

**driver 模式补充**:
- driver_name
- driver_id_number
- driver_phone
- license_plate（车牌号）

**logistics 模式补充**:
- license_plate（此时存物流公司名）

**可选**:
- delegation_id（提货委托 ID，可空，后续补填）
- notes

**系统自动填**:
- dispatch_number：`DD-YYYYMMDD-NNN`，如果工单已有同组（相同品牌/型号/提货地）调度则用 NNN，否则根据拆分规则加 `-A/-B/-C` 后缀

### 前置条件

1. 关联工单存在、未删除、状态 = normal
2. 业务员有权限

### 业务规则校验

**硬规则（error）**:
- `load_tons > 0`
- 本工单累计 dispatches.load_tons ≤ 工单 quantity_tons
- dispatch_mode = 'driver' 时：license_plate 建议非空
- dispatch_mode = 'logistics' 时：license_plate 必填（存物流公司名）

**软规则（warning）**:
- 调度品牌 ≠ 合同品牌 → 提醒（业务允许，但记录偏离）
- 调度型号 ≠ 合同型号 → 提醒
- 调度提货地 ≠ 合同提货地 → 提醒

### 拆分规则（重要）

同一工单下，**品牌 / 型号 / 提货地 任一不同必须拆成多条调度**。

**操作序列**（业务员开一条调度时）:

1. 查询该工单下已有的所有调度记录
2. 按 `(brand_id, product_model, delivery_location_id)` 分组
3. 检查本次请求的三元组是否与某组匹配：
   - 匹配 → 用该组对应的基础编号（如 `DD-20260405-001`），不加后缀（或续用 A/B/C）
   - 不匹配 → 生成新的后缀（-A / -B / -C / ...）
4. INSERT dispatches 和 dispatches_history

### 异常分支

**场景 A：超过工单剩余量**
- 硬拒绝，提示剩余 X 吨

**场景 B：一次填多条调度**
- 业务员说"分 3 车，都是 33 吨"
- AI 生成 3 个调度 operations，一个 Plan 执行完

**场景 C：一车多型号**
- 业务员说"一车 33 吨，22 吨 302 + 11 吨 328"
- AI 生成 2 条调度 operations（同 dispatch_number 基础部分 + 后缀 A/B）

### 审批要求
- 默认无需审批（物流层面的操作）

### 自然语言回复模板

```
操作预览 — 创建调度

📋 工单 THGD-20260405-001 新增 1 条调度

🚚 调度 DD-20260420-015
• 司机：刘全（皖B12971，手机 138****6433）
• 装载量：33 吨
• 品牌 × 型号：三房巷 CZ-302
• 提货地：江阴
• 提货日期：2026-04-22

⚠️ 调度品牌/型号/提货地与合同一致 ✓

确认创建吗？[确认] [取消]
```

---

## 附录 A: Workflow 权限矩阵

| Workflow | sales | purchase | broker | clerk | finance | admin | boss |
|---------|:-----:|:--------:|:------:|:-----:|:-------:|:-----:|:----:|
| create_sales_contract | ✓ | | ✓ | | | ✓ | ✓ |
| create_purchase_contract | | ✓ | ✓ | | | ✓ | ✓ |
| create_brokering_contract | ✓ | ✓ | ✓ | | | ✓ | ✓ |
| update_contract_quantity | ✓* | ✓* | ✓* | | | ✓ | ✓ |
| update_contract_price | ✓* | ✓* | ✓* | | | ✓ | ✓ |
| cancel_contract | ✓* | ✓* | ✓* | | | ✓ | ✓ |
| soft_delete_contract | | | | | | ✓ | ✓ |
| create_delivery_order | ✓ | | | ✓ | | ✓ | ✓ |
| create_delivery_delegation | | ✓ | | ✓ | | ✓ | ✓ |
| create_dispatch | ✓ | ✓ | | ✓ | | ✓ | ✓ |

`✓*` 表示只能操作自己负责的合同（scope_filter: owner_user_id = current_user）
`✓` 表示全部可操作

---

## 附录 B: 审批规则矩阵

| Workflow | 金额阈值 | 审批级别 | 审批人 |
|---------|---------|---------|-------|
| create_sales_contract | < 50 万 | 无 | - |
| create_sales_contract | 50-200 万 | 一级 | 部门主管 |
| create_sales_contract | > 200 万 | 二级 | 部门主管 + 老板 |
| create_purchase_contract | < 30 万 | 无 | - |
| create_purchase_contract | 30-150 万 | 一级 | 部门主管 |
| create_purchase_contract | > 150 万 | 二级 | 部门主管 + 老板 |
| create_brokering_contract | 佣金 < 10 万 | 无 | - |
| create_brokering_contract | 佣金 ≥ 10 万 | 一级 | 部门主管 |
| update_contract_quantity | 变化 ≤ 10% | 无 | - |
| update_contract_quantity | 10-30% | 一级 | 部门主管 |
| update_contract_quantity | > 30% | 二级 | 部门主管 + 老板 |
| update_contract_price | 任意 | 二级 | 部门主管 + 老板 |
| cancel_contract | < 100 万 | 一级 | 部门主管 |
| cancel_contract | ≥ 100 万 | 二级 | 部门主管 + 老板 |
| soft_delete_contract | 任意 | 二级 | 部门主管 + 老板 |
| create_delivery_order | < 50 万 | 无 | - |
| create_delivery_order | ≥ 50 万 | 一级 | 部门主管 |
| create_delivery_delegation | 无 | 无 | - |
| create_dispatch | 无 | 无 | - |

金额阈值具体数字可在 `approval_rules` 表配置。

---

## 附录 C: Workflow 实现顺序（配合 12 周计划）

- **W3**：create_sales_contract + update_contract_quantity（打通 Plan 生成和执行）
- **W8**：create_purchase_contract + create_brokering_contract + update_contract_price + cancel_contract + soft_delete_contract
- **W9**：create_delivery_order + create_delivery_delegation + create_dispatch

---

*v0.1 - 2026-04-20 第一版，基础 10 个 workflow*
*下一版本：补充流水导入 workflow + Phase 2 的拆分合同等复杂场景*
