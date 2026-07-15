---
category: solution
doc_id: medication_related_v1
title: 药物或慢病相关型
---

# 药物或慢病相关型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

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
    {
      "icon": "📋",
      "title": "记录用药史",
      "content": "把长期用药清单带给医生,评估药物对骨代谢的影响。"
    },
    {
      "icon": "🛡",
      "title": "防跌倒",
      "content": "药物可能影响平衡能力,尤其夜间起夜注意安全。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥛",
      "title": "钙",
      "content": "每日 800-1000mg,与药物服用时间错开 2 小时。"
    },
    {
      "icon": "🐟",
      "title": "维生素 D",
      "content": "与医生确认补充剂量,部分慢病患者需要更高剂量。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "不要自行停药",
      "content": "激素、抗凝药等是治疗原发病的关键,停药风险远大于骨质疏松。"
    },
    {
      "icon": "🚨",
      "title": "建议多学科会诊",
      "content": "原发病专科 + 骨质疏松门诊共同制定方案。"
    }
  ]
}
```

## 关键字段说明

- `id`:量表/方案唯一 ID
- `tag`:方案归类 tag,前端分类与 LLM 输出对齐用
- `riskLevel` / `risk_level`:low / medium / high / urgent
- `lifestyle` / `nutrition` / `alert`:三类建议内容

## 数据来源

AI健康咨询模块场景GPT对话1.docx (P454-465 骨密度 12 题, P551-581 腿疼 A 表 7 题, P613-650 腿疼 B 表 4 题, P1336-1348 腿疼 C 表 3 题, P466-479 骨密度建议, P683-746 腿疼归类)。
