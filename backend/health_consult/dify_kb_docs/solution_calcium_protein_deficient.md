---
category: solution
doc_id: calcium_protein_deficient_v1
title: 钙和蛋白摄入不足型
---

# 钙和蛋白摄入不足型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "calcium_protein_deficient_v1",
  "scene": "report",
  "tag": "calcium_protein_deficient",
  "title": "钙和蛋白摄入不足型",
  "riskLevel": "low",
  "department": "营养科 / 骨质疏松门诊",
  "oneLineConclusion": "您的骨量下降与饮食结构有关,先从调整餐盘开始,效果安全可预期。",
  "lifestyle": [
    {
      "icon": "🍽",
      "title": "规律三餐",
      "content": "避免长期节食或单一饮食,保证每天 3 餐结构完整。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥛",
      "title": "高钙食物",
      "content": "牛奶 300-500ml/天,豆腐 100g、深绿叶蔬菜 200g。"
    },
    {
      "icon": "🥚",
      "title": "优质蛋白",
      "content": "鸡蛋 1-2 个/天,鱼禽肉 100-150g,支持骨基质。"
    },
    {
      "icon": "🥜",
      "title": "镁和维生素 K",
      "content": "坚果、菠菜、西兰花,帮助钙沉积到骨骼。"
    }
  ],
  "alert": [
    {
      "icon": "💡",
      "title": "减盐",
      "content": "高盐饮食加速钙流失,每日盐 < 5g。"
    },
    {
      "icon": "💡",
      "title": "少酒",
      "content": "过量饮酒抑制成骨细胞,建议女性每日酒精 < 15g。"
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
