# 常见问题解答 FAQ — `<DATASET_FAQ>`

> 来源: `32-6.17/常见问题解答.xlsx`(49 条,21 个功能节点分组)
> 用途: FAQ 直查(SPEC-B1 5002-2) + 流程2 multi_retrieval 兜底
> 语言: **英文为主**(xlsx 原文是英文),国内用户走中文反向映射命中

## 21 个功能节点(与 xlsx 严格对齐)

```
Role Management / Shop Level / Individual operator / Operator review for entry
/ Add sites under the operator / Site audit / Billing Template / Charging Order
/ Charging coupons / Create venue / Data View / Data sector / Equipment Failure List
/ Financial Management / Operations Management / Order Management / Placement equipment
/ Real name authentication / Sign up / Venue / Venue association template
/ equipment / place an order / top-up
```

## 字段结构(每条 FAQ)

| 列 | 类型 | 说明 |
|----|------|------|
| `node` | string | 21 节点之一 |
| `question_en` | string | 英文问题 |
| `question_zh` | string | 中文问题(回填) |
| `answer_en` | text | 英文答案(原文) |
| `answer_zh` | text | 中文答案(回填) |
| `related_manual_chapter` | string | 关联手册 35 标题之一 |
| `tags` | list | 检索标签 |

## 占位样例(从 xlsx 实际 49 条摘要)

### node: Role Management(3 条)

**Q1**: Enter the system 后,Role Management 支持哪些 End type 与角色类型?
**A1**: 系统支持 Backend 等 End type,可配置租户管理员、站点管理员、财务、运营等角色类型
**related_manual_chapter**: Role Management

**Q2**: 角色权限分配的粒度可以到什么级别?
**A2**: 权限分配支持按模块菜单独立勾选,覆盖 Operation、Partner、Shop、Member、Marketing...
**related_manual_chapter**: Role Management

**Q3**: 角色创建保存后,End type 支持修改吗?
**A3**: 不支持修改,若需调整需重新创建对应类型的角色
**related_manual_chapter**: Role Management

### node: Billing Template(6 条,占比最高)

**Q1**: 计费模板创建后就直接生效吗?
**A1**: 计费模板创建后需关联对应站点方可生效
**related_manual_chapter**: Billing Template (Charging Station)

**Q2**: Duration minimum start amount 的具体作用是什么?
**A2**: 该参数为最低启动余额阈值,用户账户余额低于设定值时无法启动充电
**related_manual_chapter**: Billing Template (Charging Station)

### node: Equipment Failure List(1 条)

**Q1**: 故障反馈支持哪些后台操作?
**A1**: 平台可对设备故障进行分类、派单、跟踪、关闭等全流程管理
**related_manual_chapter**: Equipment Failure List

### node: Operations Management(1 条)

**Q1**: 协议配置启用后也可以多语言展示不同吗?
**A1**: 是的,平台支持按用户语言展示不同的用户协议
**related_manual_chapter**: Operations Management

## 中文反向映射(便于中文用户命中)

详见 `backend/charge_consult/scene_router.py` 的 `_FAQ_NODE_ZH_HINTS` 字典,与本库 21 节点保持一致。

## 待补充

- [ ] 从 xlsx 提取完整 49 条问答
- [ ] 中文问答回填(由国内运营团队提供)
- [ ] 关联到 product_spec.md 的 func_id
- [ ] 关联到 operation_guide_*.md 的章节
