---
category: solution
doc_id: exercise_deficient_v1
title: 缺乏运动/肌力不足型
---

# 缺乏运动/肌力不足型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "exercise_deficient_v1",
  "scene": "report",
  "tag": "exercise_deficient",
  "title": "缺乏运动/肌力不足型",
  "riskLevel": "low",
  "department": "康复科 / 骨质疏松门诊",
  "oneLineConclusion": "您的骨量下降与长期缺乏运动相关,合适的负重训练能有效逆转趋势。",
  "lifestyle": [
    {
      "icon": "🏋",
      "title": "力量训练",
      "content": "每周 2-3 次深蹲、弹力带、抗阻训练,刺激骨骼重塑。"
    },
    {
      "icon": "🚶",
      "title": "规律有氧",
      "content": "快走、慢跑、太极、跳舞,每次 30 分钟,每周 150 分钟以上。"
    },
    {
      "icon": "🧘",
      "title": "平衡训练",
      "content": "单脚站立、太极,降低跌倒和骨折风险。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥛",
      "title": "钙和蛋白",
      "content": "运动后补充牛奶或酸奶,帮助肌肉和骨骼恢复。"
    }
  ],
  "alert": [
    {
      "icon": "⚠",
      "title": "循序渐进",
      "content": "骨质疏松者避免突然剧烈运动和深蹲大重量,先评估再上强度。"
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
