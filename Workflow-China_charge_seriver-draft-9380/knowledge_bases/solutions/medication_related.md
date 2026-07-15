---
dataset: solution
solution_id: medication_related_v1
tag: medication_related
scene: report
risk_level: high
department: 内分泌科 / 相关慢病专科
updated: 2026-06-17
---

# 药物或慢病相关型

## 一句话结论
您的骨量下降与长期用药或慢性病相关,需要专科医生综合评估治疗方案。

## 生活方式建议
- 📋 记录用药史:把长期用药清单带给医生,评估药物对骨代谢的影响。
- 🛡 防跌倒:药物可能影响平衡能力,尤其夜间起夜注意安全。

## 营养建议
- 🥛 钙:每日 800-1000mg,与药物服用时间错开 2 小时。
- 🐟 维生素 D:与医生确认补充剂量,部分慢病患者需要更高剂量。

## 警示与就医
- 🚨 不要自行停药:激素、抗凝药等是治疗原发病的关键,停药风险远大于骨质疏松。
- 🚨 建议多学科会诊:原发病专科 + 骨质疏松门诊共同制定方案。

## JSON
```json
{
  "id": "medication_related_v1",
  "scene": "report",
  "tag": "medication_related",
  "title": "药物或慢病相关型",
  "riskLevel": "high",
  "department": "内分泌科 / 相关慢病专科",
  "oneLineConclusion": "您的骨量下降与长期用药或慢性病相关,需要专科医生综合评估治疗方案。",
  "lifestyle": [
    { "icon": "📋", "title": "记录用药史", "content": "把长期用药清单带给医生,评估药物对骨代谢的影响。" },
    { "icon": "🛡", "title": "防跌倒", "content": "药物可能影响平衡能力,尤其夜间起夜注意安全。" }
  ],
  "nutrition": [
    { "icon": "🥛", "title": "钙", "content": "每日 800-1000mg,与药物服用时间错开 2 小时。" },
    { "icon": "🐟", "title": "维生素 D", "content": "与医生确认补充剂量,部分慢病患者需要更高剂量。" }
  ],
  "alert": [
    { "icon": "🚨", "title": "不要自行停药", "content": "激素、抗凝药等是治疗原发病的关键,停药风险远大于骨质疏松。" },
    { "icon": "🚨", "title": "建议多学科会诊", "content": "原发病专科 + 骨质疏松门诊共同制定方案。" }
  ]
}
```
