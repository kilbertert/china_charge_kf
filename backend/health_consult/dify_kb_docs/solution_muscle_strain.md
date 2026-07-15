---
category: solution
doc_id: muscle_strain_v1
title: 肌肉劳损/运动过度型
---

# 肌肉劳损/运动过度型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "muscle_strain_v1",
  "scene": "symptom",
  "tag": "muscle_strain",
  "title": "肌肉劳损/运动过度型",
  "riskLevel": "low",
  "department": "康复科 / 骨科",
  "oneLineConclusion": "您的情况更像是肌肉劳损或运动后疲劳相关,先休息和拉伸,一般 1-2 周可缓解。",
  "lifestyle": [
    {
      "icon": "🛌",
      "title": "适当休息",
      "content": "暂停高强度运动 3-7 天,疼痛明显时减少负重。"
    },
    {
      "icon": "🧘",
      "title": "拉伸放松",
      "content": "疼痛缓解后做股四头肌、腘绳肌、小腿拉伸,每次 15-30 秒。"
    },
    {
      "icon": "🔥",
      "title": "热敷",
      "content": "慢性酸痛可热敷 15-20 分钟,促进血液循环。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥚",
      "title": "优质蛋白",
      "content": "帮助肌肉修复,鸡蛋、鱼禽肉、豆制品。"
    },
    {
      "icon": "💧",
      "title": "充足水分",
      "content": "每日 1500-2000ml,运动后适量补充电解质。"
    }
  ],
  "alert": [
    {
      "icon": "💡",
      "title": "观察 1-2 周",
      "content": "如疼痛不减轻或加重,需重新评估。"
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
