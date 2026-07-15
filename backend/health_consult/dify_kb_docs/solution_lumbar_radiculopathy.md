---
category: solution
doc_id: lumbar_radiculopathy_v1
title: 腰椎神经牵涉型
---

# 腰椎神经牵涉型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "lumbar_radiculopathy_v1",
  "scene": "symptom",
  "tag": "lumbar_radiculopathy",
  "title": "腰椎神经牵涉型",
  "riskLevel": "medium",
  "department": "骨科 / 脊柱外科 / 康复科",
  "oneLineConclusion": "您的情况更像是腰椎相关神经受刺激,需要先明确诊断,避免久坐和错误姿势。",
  "lifestyle": [
    {
      "icon": "🪑",
      "title": "避免久坐",
      "content": "每 30-40 分钟起身活动,坐姿保持腰部有支撑。"
    },
    {
      "icon": "🧘",
      "title": "核心训练",
      "content": "平板支撑、桥式、鸟狗式,增强腰腹肌力。"
    },
    {
      "icon": "🛌",
      "title": "睡姿调整",
      "content": "侧卧时双膝间夹枕,仰卧时膝下垫枕,减轻腰椎压力。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥛",
      "title": "钙和维生素 D",
      "content": "保护腰椎骨骼基础,每日 800-1000mg 钙。"
    },
    {
      "icon": "🥦",
      "title": "维生素 B 族",
      "content": "全谷物、绿叶菜,帮助神经修复。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "建议就医",
      "content": "骨科或脊柱外科,医生可能需要 MRI 评估椎间盘和神经。"
    },
    {
      "icon": "🚨",
      "title": "紧急就医",
      "content": "若出现大小便异常、腿麻无力明显加重、马鞍区麻木,立即急诊(可能为马尾综合征)。"
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
