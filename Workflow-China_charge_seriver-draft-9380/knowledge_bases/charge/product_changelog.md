# 版本变更日志 — `<DATASET_PRODUCT_CHANGELOG>`

> 来源: V2.0 → V2.4.1 真实版本历史
> 用途: 流程2 — 清单准确性校验(SPEC-C2,节点 5013/5014)
> 检索策略: multi_retrieval, weights 0.5(本库) + 0.5(`<DATASET_FAQ>`)

## 字段结构

| 列 | 类型 | 说明 |
|----|------|------|
| `version` | string | 版本号 X.Y.Z |
| `date` | date | 变更日期 ISO8601 |
| `category` | enum | 板块 |
| `module` | string | 模块名 |
| `function_name` | string | 受影响功能点 |
| `change_type` | enum | add / modify / remove / deprecate |
| `before` | text | 变更前描述 |
| `after` | text | 变更后描述 |
| `impact` | enum | low / medium / high / breaking |
| `author` | string | 编写人 |

## 真实版本历史(占位 — 后续按行填充细节)

| 版本 | 日期 | 更新内容(摘要) | 影响范围 |
|------|------|----------------|----------|
| V2.0 | 2025-11-05 | 功能清单 2.0 初稿整理 | — |
| V2.1 | 2026-04-28 | 新增海外充电用户端功能清单 | 海外功能矩阵扩展 |
| V2.2 | 2026-05-15 | 新增海外运营商管家端和海外 PC 端后台功能清单 | 海外管家/后台 |
| V2.3 | 2026-05-22 | 海外版本取消二轮充电;优化线上分账和提现 | 海外二轮场景下线 |
| V2.4 | 2026-06-12 | 新增家充功能清单 | 国内家充场景 |
| V2.4.1 | 2026-06-15 | 删除家充场景下后台用户管理的充值功能 | 家充充值流程调整 |

## 占位样例

### V2.4.1 — 家充后台充值功能删除

```
version: V2.4.1
date: 2026-06-15
category: 家充
module: 家充-PC 管理后台
function_name: 用户充值
change_type: remove
before: 家充用户可在管理后台进行充值操作
after: 家充用户充值入口已下线,统一通过用户端操作
impact: medium
author: 周向荣
```

### V2.3 — 海外二轮充电下线

```
version: V2.3
date: 2026-05-22
category: 首页
module: 充电站列表
function_name: 电动车充电桩
change_type: remove
before: 海外版本支持二轮充电桩列表
after: 海外版本不再展示二轮充电相关业务
impact: high
author: 周向荣
```

## 校验逻辑(5014 code 节点)

```python
def verify_changelog(function_name: str, claimed_version: str) -> bool:
    """检查用户问的功能在当前最新版本是否仍然有效。

    Returns:
        True: 功能存在,版本号匹配
        False: 功能被删除或版本不匹配
    """
    # 从本库 latest entry 中查
    ...
```

## 待补充

- [ ] 每个 V2.x 版本的全部功能点 diff(约 50+ 条)
- [ ] 标注"影响范围"对应的用户群体
- [ ] 引用 product_spec.md 的 func_id 建立双向链接
