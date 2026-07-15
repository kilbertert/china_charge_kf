# 故障诊断手册 — `<DATASET_FAULT_DIAGNOSIS>`

> 用途: 路径 B 业务诊断(SPEC-D2,节点 5021,multi_retrieval 权重 0.2)
> 触发: scene=after_sales 且危险信号未命中(否则走 5022 紧急路径)

## 字段结构

| 列 | 类型 | 说明 |
|----|------|------|
| `fault_code` | string | 故障码,如 F001 |
| `category` | enum | 充电中断 / 通讯故障 / 硬件故障 / 计费异常 / 支付异常 / 系统异常 |
| `phenomenon_zh` | text | 现象描述(中文) |
| `phenomenon_en` | text | 现象描述(英文) |
| `possible_causes` | list | 可能原因 |
| `troubleshooting_steps` | list | 排查步骤(顺序) |
| `fallback_action` | text | 兜底建议(无法自助解决时) |
| `related_danger_keyword` | string | 关联后端危险信号关键词 |

## 占位样例

### F001 — 充电中断

```
fault_code: F001
category: 充电中断
phenomenon_zh: 充电过程中突然中断,App 显示"充电已结束"
phenomenon_en: Charging interrupted mid-way, App shows "Charging ended"
possible_causes:
  - 充电枪脱落
  - 设备过温保护
  - 余额不足
  - 通讯中断
troubleshooting_steps:
  1. 检查充电枪是否插紧
  2. 查看 App 错误码
  3. 检查账户余额
  4. 重启设备(断电 30s)
fallback_action: 如以上步骤未解决,请联系平台技术支持并提供错误码
related_danger_keyword: 充电中断
```

### F002 — 扫码识别不到设备

```
fault_code: F002
category: 通讯故障
phenomenon_zh: 扫描设备二维码后,App 无反应或显示"设备不存在"
phenomenon_en: After scanning device QR, App unresponsive
possible_causes:
  - 二维码破损
  - 设备未投放
  - 网络问题
troubleshooting_steps:
  1. 清洁二维码
  2. 手动输入设备编号
  3. 检查网络连接
fallback_action: 联系现场工作人员
related_danger_keyword: —
```

### F003 — 余额不足

```
fault_code: F003
category: 计费异常
phenomenon_zh: 启动充电时提示余额不足
phenomenon_en: Insufficient balance when starting charge
possible_causes:
  - 余额确实不足
  - 充值未到账
troubleshooting_steps:
  1. App 充值
  2. 等待 5 分钟到账
  3. 联系客服查询
fallback_action: —
related_danger_keyword: 余额不足
```

### F004 — 设备离线

```
fault_code: F004
category: 通讯故障
phenomenon_zh: 管家端显示设备长时间离线
phenomenon_en: Device shows offline for extended period
possible_causes:
  - 网络断开
  - SIM 卡欠费
  - 设备断电
troubleshooting_steps:
  1. 检查现场网络
  2. 检查 SIM 卡状态
  3. 检查电源
fallback_action: 现场技术人员上门
related_danger_keyword: 设备离线
```

## 与危险信号的差异

- **危险信号**(`backend/charge_consult/danger_signals.py`): 物理安全(漏电/冒烟),命中走 5022 紧急路径
- **故障诊断**(本库): 一般性功能故障,命中走 5021 LLM 业务诊断

## 待补充

- [ ] 从实际工单系统中导出高频故障码
- [ ] 与产品运营对齐故障码命名规范
- [ ] 增加海外版特有故障(payment gateway 异常等)
