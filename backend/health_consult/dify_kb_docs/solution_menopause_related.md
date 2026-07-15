---
category: solution
doc_id: menopause_related_v1
title: 年龄/绝经相关骨量流失型
---

# 年龄/绝经相关骨量流失型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "menopause_related_v1",
  "scene": "report",
  "tag": "menopause_related",
  "title": "年龄/绝经相关骨量流失型",
  "riskLevel": "medium",
  "department": "内分泌科 / 骨质疏松门诊",
  "oneLineConclusion": "您的骨量下降与年龄和绝经后激素变化相关,需要专业评估和系统管理。",
  "lifestyle": [
    {
      "icon": "☀",
      "title": "规律日晒",
      "content": "每天 15-30 分钟,暴露前臂和小腿,促进维生素 D 合成。"
    },
    {
      "icon": "🚶",
      "title": "负重运动",
      "content": "每周 3-5 次快走、慢跑、太极或跳舞,促进成骨细胞活性。"
    },
    {
      "icon": "🛡",
      "title": "防跌倒",
      "content": "居家防滑、避免提重物、注意夜间起夜安全,保护髋部和腰椎。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥛",
      "title": "钙",
      "content": "每日 800-1000mg,优先食补:牛奶、酸奶、豆腐、深绿叶蔬菜。"
    },
    {
      "icon": "🐟",
      "title": "维生素 D",
      "content": "每日 400-800IU,严重缺乏者需医生处方大剂量补充。"
    },
    {
      "icon": "🥚",
      "title": "优质蛋白",
      "content": "每日 1.0-1.2g/kg,支持骨基质合成。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "建议就医",
      "content": "到内分泌科或骨质疏松门诊评估是否需要骨密度复查和药物治疗。"
    },
    {
      "icon": "⚠",
      "title": "重点检查",
      "content": "25-OH 维生素 D、血钙、血磷、肾功能、PTH、骨代谢标志物。"
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
