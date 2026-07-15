---
dataset: solution
solution_id: vitamin_d_deficient_v1
tag: vitamin_d_deficient
scene: report
risk_level: medium
department: 内分泌科
updated: 2026-06-17
---

# 维生素D不足/日晒不足型

## 一句话结论
您的骨量下降与维生素 D 不足高度相关,补 D 是当下最直接可做的事。

## 生活方式建议
- ☀ 增加日晒:上午 10 点至下午 3 点,每周 3 次,每次 15-30 分钟裸露前臂。
- 🏃 户外活动:把室内运动换成散步、慢跑、园艺,运动和日晒一举两得。

## 营养建议
- 🐟 维生素 D:优先食补(三文鱼、沙丁鱼、蛋黄、动物肝脏);不足时按医嘱补充。
- 🥛 钙:每日 800-1000mg,维生素 D 不足时钙吸收率会下降。

## 警示与就医
- 🚨 建议查血:抽血查 25-OH 维生素 D,目标值 30-50ng/mL。
- ⚠ 不要自行大剂量补:高剂量维生素 D 长期服用可能中毒,需医生评估后处方。

## JSON
```json
{
  "id": "vitamin_d_deficient_v1",
  "scene": "report",
  "tag": "vitamin_d_deficient",
  "title": "维生素D不足/日晒不足型",
  "riskLevel": "medium",
  "department": "内分泌科",
  "oneLineConclusion": "您的骨量下降与维生素 D 不足高度相关,补 D 是当下最直接可做的事。",
  "lifestyle": [
    { "icon": "☀", "title": "增加日晒", "content": "上午 10 点至下午 3 点,每周 3 次,每次 15-30 分钟裸露前臂。" },
    { "icon": "🏃", "title": "户外活动", "content": "把室内运动换成散步、慢跑、园艺,运动和日晒一举两得。" }
  ],
  "nutrition": [
    { "icon": "🐟", "title": "维生素 D", "content": "优先食补:三文鱼、沙丁鱼、蛋黄、动物肝脏;不足时按医嘱补充。" },
    { "icon": "🥛", "title": "钙", "content": "每日 800-1000mg,维生素 D 不足时钙吸收率会下降。" }
  ],
  "alert": [
    { "icon": "🚨", "title": "建议查血", "content": "抽血查 25-OH 维生素 D,目标值 30-50ng/mL。" },
    { "icon": "⚠", "title": "不要自行大剂量补", "content": "高剂量维生素 D 长期服用可能中毒,需医生评估后处方。" }
  ]
}
```
