---
dataset: solution
solution_id: osteoporosis_risk_v1
tag: osteoporosis_risk
scene: symptom
risk_level: high
department: 骨科 / 骨质疏松门诊
updated: 2026-06-17
---

# 骨质疏松/骨折风险型

## 一句话结论
您的情况可能与骨质疏松或隐匿骨折相关,需要影像学确认和骨密度评估。

## 生活方式建议
- 🛡 重点防跌倒:居家防滑、夜间照明、外出防滑鞋。
- 🚶 避免高风险动作:不提重物、不弯腰搬物、不突然扭转。

## 营养建议
- 🥛 钙:每日 1000-1200mg,饮食+补充剂。
- 🐟 维生素 D:维持 25-OH D 在 30ng/mL 以上。
- 🥚 优质蛋白:支持骨基质,每日 1.0-1.2g/kg。

## 警示与就医
- 🚨 建议就医:骨科或骨质疏松门诊,可能需要 X 光和 DXA 骨密度检查。
- 🚨 紧急就医:轻微外伤后明显疼痛、身高变矮、腰背剧痛,需立即排查骨折。

## JSON
```json
{
  "id": "osteoporosis_risk_v1",
  "scene": "symptom",
  "tag": "osteoporosis_risk",
  "title": "骨质疏松/骨折风险型",
  "riskLevel": "high",
  "department": "骨科 / 骨质疏松门诊",
  "oneLineConclusion": "您的情况可能与骨质疏松或隐匿骨折相关,需要影像学确认和骨密度评估。",
  "lifestyle": [
    { "icon": "🛡", "title": "重点防跌倒", "content": "居家防滑、夜间照明、外出防滑鞋。" },
    { "icon": "🚶", "title": "避免高风险动作", "content": "不提重物、不弯腰搬物、不突然扭转。" }
  ],
  "nutrition": [
    { "icon": "🥛", "title": "钙", "content": "每日 1000-1200mg,饮食+补充剂。" },
    { "icon": "🐟", "title": "维生素 D", "content": "维持 25-OH D 在 30ng/mL 以上。" },
    { "icon": "🥚", "title": "优质蛋白", "content": "支持骨基质,每日 1.0-1.2g/kg。" }
  ],
  "alert": [
    { "icon": "🚨", "title": "建议就医", "content": "骨科或骨质疏松门诊,可能需要 X 光和 DXA 骨密度检查。" },
    { "icon": "🚨", "title": "紧急就医", "content": "轻微外伤后明显疼痛、身高变矮、腰背剧痛,需立即排查骨折。" }
  ]
}
```
