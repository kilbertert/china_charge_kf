# 操作手册 中文版 — <DATASET_OPERATION_GUIDE> (zh)

> 来源: 中译英版 docx 194 段 + 英文原版 docx 35 章节  
> 用途: SPEC-D3 路径 C 操作指导, 节点 5030 KR + 5031 LLM + 5032 链接保留  
> 检索: multi_retrieval, metadata filter language=zh

## 35 章节 × 3 端分布

### PC 管理后台(16 章节)
- Role Management / Shop Level / Individual operator
- Operator review for entry / Add sites under the operator / Site audit
- Billing Template (Charging Station) / Add product model / equipment
- Placement equipment / Charging coupons / Equipment Failure List
- User Management / Financial Management / Order Management
- Operations Management / Data View

### 用户端 C 端(9 章节)
- Sign up / top-up / place an order
- Four wheel charging order / Placeholder fee order
- venue / license plate / Change password / Fault Repair

### 管家端 B 端(10 章节)
- Sign up / Real name authentication / Create venue / my venue
- Create template / Venue association template / Placement equipment
- data sector / order / Venue details / Profit withdrawal

## 字段结构

| 列 | 类型 | 说明 |
|----|------|------|
| chapter | string | 35 一级标题 |
| endpoint | enum | user / butler / pc |
| step | int | 步骤序号 |
| step_text_zh | text | 中文步骤 |
| deep_link | string | 跳转路径 |
| notes | text | 备注 |

## 占位样例

### Role Management (pc) 步骤 1-3
1. 进入系统 → 角色管理
2. 点击"添加"按钮以添加角色
3. 填写表格:选择结束类型、角色名称、角色类型及角色代码,然后点击"保存"

### Fault Repair (user) 故障报修
1. 打开 App,点击"我的" → "故障报修"
- deep_link: /charge/pages/malfunction/malfunction
- 5032 节点必须保留此链接

### Placeholder fee order (user) 占位费
1. 在占位费订单页面查看费用明细
- deep_link: /charge/pages/placeUseFeeList/placeUseFeeList
- 5032 必须保留

### Profit withdrawal (butler) 收益提现
1. 管家端首页 → 我的 → 收益提现
2. 填写提现金额 → 银行卡 → 提交审核
- notes: T+1 到账

## 关键约束(5032)

⚠️ deep_link 字符串必须原样保留:
- /charge/pages/malfunction/malfunction
- /charge/pages/placeUseFeeList/placeUseFeeList
- /admin/system/role
- ... 30+ 链接

## 待补充
- [ ] 35 章节完整步骤提取(200+ 步)
- [ ] deep_link 全量补充
- [ ] 与 FAQ 21 节点交叉引用
