---
category: solution
doc_id: vitamin_d_deficient_v1
title: 维生素D不足/日晒不足型
---

# 维生素D不足/日晒不足型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

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
    {
      "icon": "☀",
      "title": "增加日晒",
      "content": "上午 10 点至下午 3 点,每周 3 次,每次 15-30 分钟裸露前臂。"
    },
    {
      "icon": "🏃",
      "title": "户外活动",
      "content": "把室内运动换成散步、慢跑、园艺,运动和日晒一举两得。"
    }
  ],
  "nutrition": [
    {
      "icon": "🐟",
      "title": "维生素 D",
      "content": "优先食补:三文鱼、沙丁鱼、蛋黄、动物肝脏;不足时按医嘱补充。"
    },
    {
      "icon": "🥛",
      "title": "钙",
      "content": "每日 800-1000mg,维生素 D 不足时钙吸收率会下降。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "建议查血",
      "content": "抽血查 25-OH 维生素 D,目标值 30-50ng/mL。"
    },
    {
      "icon": "⚠",
      "title": "不要自行大剂量补",
      "content": "高剂量维生素 D 长期服用可能中毒,需医生评估后处方。"
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
