---
dataset: solution
solution_id: vascular_risk_v1
tag: vascular_risk
scene: symptom
risk_level: high
department: 血管外科 / 急诊
updated: 2026-06-17
---

# 血管循环风险型

## 一句话结论
您的情况可能与血管相关风险有关,需要优先排除血栓和循环问题,不能拖延。

## 生活方式建议
- 🛌 避免按摩:小腿肿胀时不要按摩或热敷,以免血栓脱落。
- 🚶 避免久坐久卧:长途旅行时每 1-2 小时起身活动。

## 营养建议
- 💧 充足水分:降低血液粘稠度,每日 1500-2000ml。

## 警示与就医
- 🚨 尽快就医:一侧小腿肿胀 + 胸闷气短需紧急排查肺栓塞;单纯小腿肿胀需排查深静脉血栓。
- 🚨 急诊指征:突然胸痛、咯血、晕厥 → 立即急诊(120)。

## JSON
```json
{
  "id": "vascular_risk_v1",
  "scene": "symptom",
  "tag": "vascular_risk",
  "title": "血管循环风险型",
  "riskLevel": "high",
  "department": "血管外科 / 急诊",
  "oneLineConclusion": "您的情况可能与血管相关风险有关,需要优先排除血栓和循环问题,不能拖延。",
  "lifestyle": [
    { "icon": "🛌", "title": "避免按摩", "content": "小腿肿胀时不要按摩或热敷,以免血栓脱落。" },
    { "icon": "🚶", "title": "避免久坐久卧", "content": "长途旅行时每 1-2 小时起身活动。" }
  ],
  "nutrition": [
    { "icon": "💧", "title": "充足水分", "content": "降低血液粘稠度,每日 1500-2000ml。" }
  ],
  "alert": [
    { "icon": "🚨", "title": "尽快就医", "content": "一侧小腿肿胀 + 胸闷气短需紧急排查肺栓塞;单纯小腿肿胀需排查深静脉血栓。" },
    { "icon": "🚨", "title": "急诊指征", "content": "突然胸痛、咯血、晕厥 → 立即急诊(120)。" }
  ]
}
```
