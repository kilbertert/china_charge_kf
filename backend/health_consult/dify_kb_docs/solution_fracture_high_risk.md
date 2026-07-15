---
category: solution
doc_id: fracture_high_risk_v1
title: 骨折高风险型
---

# 骨折高风险型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

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
    {
      "icon": "🛡",
      "title": "重点防跌倒",
      "content": "家中加装扶手、防滑垫、感应灯;外出穿防滑鞋。"
    },
    {
      "icon": "🚶",
      "title": "避免高风险动作",
      "content": "不搬重物、不弯腰提物、不做突然扭转。"
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
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "尽快就医",
      "content": "建议在 1 个月内到骨质疏松门诊或骨科评估,询问是否需要双膦酸盐、地舒单抗等治疗。"
    },
    {
      "icon": "🚨",
      "title": "紧急就医",
      "content": "若出现身高变矮明显、腰背剧痛或轻微摔倒后疼痛,立即就诊排除骨折。"
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
