---
category: solution
doc_id: osteoporosis_risk_v1
title: 骨质疏松/骨折风险型
---

# 骨质疏松/骨折风险型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

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
    {
      "icon": "🛡",
      "title": "重点防跌倒",
      "content": "居家防滑、夜间照明、外出防滑鞋。"
    },
    {
      "icon": "🚶",
      "title": "避免高风险动作",
      "content": "不提重物、不弯腰搬物、不突然扭转。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥛",
      "title": "钙",
      "content": "每日 1000-1200mg,饮食+补充剂。"
    },
    {
      "icon": "🐟",
      "title": "维生素 D",
      "content": "维持 25-OH D 在 30ng/mL 以上。"
    },
    {
      "icon": "🥚",
      "title": "优质蛋白",
      "content": "支持骨基质,每日 1.0-1.2g/kg。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "建议就医",
      "content": "骨科或骨质疏松门诊,可能需要 X 光和 DXA 骨密度检查。"
    },
    {
      "icon": "🚨",
      "title": "紧急就医",
      "content": "轻微外伤后明显疼痛、身高变矮、腰背剧痛,需立即排查骨折。"
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
