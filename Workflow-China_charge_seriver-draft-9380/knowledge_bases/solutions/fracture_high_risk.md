---
dataset: solution
solution_id: fracture_high_risk_v1
tag: fracture_high_risk
scene: report
risk_level: high
department: 骨科 / 骨质疏松门诊
updated: 2026-06-17
---

# 骨折高风险型

## 一句话结论
您存在多项骨折高风险因素,需要尽快评估是否启动抗骨松药物治疗。

## 生活方式建议
- 🛡 重点防跌倒:家中加装扶手、防滑垫、感应灯;外出穿防滑鞋。
- 🚶 避免高风险动作:不搬重物、不弯腰提物、不做突然扭转。

## 营养建议
- 🥛 钙:每日 1000-1200mg,饮食+补充剂。
- 🐟 维生素 D:维持 25-OH D 在 30ng/mL 以上。

## 警示与就医
- 🚨 尽快就医:建议在 1 个月内到骨质疏松门诊或骨科评估,询问是否需要双膦酸盐、地舒单抗等治疗。
- 🚨 紧急就医:若出现身高变矮明显、腰背剧痛或轻微摔倒后疼痛,立即就诊排除骨折。

## JSON
```json
{
  "id": "fracture_high_risk_v1",
  "scene": "report",
  "tag": "fracture_high_risk",
  "title": "骨折高风险型",
  "riskLevel": "high",
  "department": "骨科 / 骨质疏松门诊",
  "oneLineConclusion": "您存在多项骨折高风险因素,需要尽快评估是否启动抗骨松药物治疗。",
  "lifestyle": [
    { "icon": "🛡", "title": "重点防跌倒", "content": "家中加装扶手、防滑垫、感应灯;外出穿防滑鞋。" },
    { "icon": "🚶", "title": "避免高风险动作", "content": "不搬重物、不弯腰提物、不做突然扭转。" }
  ],
  "nutrition": [
    { "icon": "🥛", "title": "钙", "content": "每日 1000-1200mg,饮食+补充剂。" },
    { "icon": "🐟", "title": "维生素 D", "content": "维持 25-OH D 在 30ng/mL 以上。" }
  ],
  "alert": [
    { "icon": "🚨", "title": "尽快就医", "content": "建议在 1 个月内到骨质疏松门诊或骨科评估,询问是否需要双膦酸盐、地舒单抗等治疗。" },
    { "icon": "🚨", "title": "紧急就医", "content": "若出现身高变矮明显、腰背剧痛或轻微摔倒后疼痛,立即就诊排除骨折。" }
  ]
}
```
