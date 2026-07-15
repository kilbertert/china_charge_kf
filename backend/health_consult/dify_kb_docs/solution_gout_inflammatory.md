---
category: solution
doc_id: gout_inflammatory_v1
title: 尿酸/痛风炎症型
---

# 尿酸/痛风炎症型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "gout_inflammatory_v1",
  "scene": "symptom",
  "tag": "gout_inflammatory",
  "title": "尿酸/痛风炎症型",
  "riskLevel": "medium",
  "department": "风湿免疫科 / 骨科",
  "oneLineConclusion": "您的情况可能与尿酸相关关节炎症有关,需要控制饮食 + 评估是否需要降尿酸治疗。",
  "lifestyle": [
    {
      "icon": "💧",
      "title": "多喝水",
      "content": "每日 2000ml 以上,促进尿酸排泄。"
    },
    {
      "icon": "🚶",
      "title": "适度活动",
      "content": "急性期卧床休息,缓解后规律低强度运动。"
    },
    {
      "icon": "⚖",
      "title": "控制体重",
      "content": "避免快速减肥,会诱发痛风发作。"
    }
  ],
  "nutrition": [
    {
      "icon": "🚫",
      "title": "低嘌呤饮食",
      "content": "避免动物内脏、海鲜汤、啤酒;适量瘦肉、豆类。"
    },
    {
      "icon": "🥬",
      "title": "多吃蔬菜",
      "content": "深绿叶菜、樱桃(有助于降尿酸)。"
    },
    {
      "icon": "🥛",
      "title": "低脂乳制品",
      "content": "帮助尿酸排泄。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "建议风湿免疫科",
      "content": "评估是否需要降尿酸药物,不要只靠饮食控制。"
    },
    {
      "icon": "🚨",
      "title": "急性发作",
      "content": "关节红肿热痛明显时,24 小时内就诊,急性期用药效果最好。"
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
