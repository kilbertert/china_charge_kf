---
category: solution
doc_id: vascular_risk_v1
title: 血管循环风险型
---

# 血管循环风险型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

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
    {
      "icon": "🛌",
      "title": "避免按摩",
      "content": "小腿肿胀时不要按摩或热敷,以免血栓脱落。"
    },
    {
      "icon": "🚶",
      "title": "避免久坐久卧",
      "content": "长途旅行时每 1-2 小时起身活动。"
    }
  ],
  "nutrition": [
    {
      "icon": "💧",
      "title": "充足水分",
      "content": "降低血液粘稠度,每日 1500-2000ml。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "尽快就医",
      "content": "一侧小腿肿胀 + 胸闷气短需紧急排查肺栓塞;单纯小腿肿胀需排查深静脉血栓。"
    },
    {
      "icon": "🚨",
      "title": "急诊指征",
      "content": "突然胸痛、咯血、晕厥 → 立即急诊(120)。"
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
