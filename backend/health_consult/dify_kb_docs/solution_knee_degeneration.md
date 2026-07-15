---
category: solution
doc_id: knee_degeneration_v1
title: 膝关节/关节退变型
---

# 膝关节/关节退变型

> 本文档为 Dify 知识库 (dataset: solution) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "knee_degeneration_v1",
  "scene": "symptom",
  "tag": "knee_degeneration",
  "title": "膝关节/关节退变型",
  "riskLevel": "medium",
  "department": "骨科 / 康复科",
  "oneLineConclusion": "您的情况更像是膝关节负重或退变相关,需要减负 + 肌力训练综合管理。",
  "lifestyle": [
    {
      "icon": "⚠",
      "title": "避免高负担动作",
      "content": "暂停爬山、深蹲、长时间上下楼、跪姿。"
    },
    {
      "icon": "🏊",
      "title": "低冲击运动",
      "content": "游泳、骑车、椭圆机、坐姿划船,保护关节。"
    },
    {
      "icon": "🏋",
      "title": "肌力训练",
      "content": "加强股四头肌和臀肌,推荐直腿抬高、靠墙静蹲(无痛范围)。"
    },
    {
      "icon": "⚖",
      "title": "控制体重",
      "content": "体重每减 5kg,膝关节负担减少约 20kg。"
    }
  ],
  "nutrition": [
    {
      "icon": "🥛",
      "title": "钙和维生素 D",
      "content": "每日钙 800-1000mg,维生素 D 400-800IU。"
    },
    {
      "icon": "🐟",
      "title": "抗炎饮食",
      "content": "深海鱼、橄榄油、坚果,减少甜食和加工肉。"
    },
    {
      "icon": "🍗",
      "title": "优质蛋白",
      "content": "支持软骨修复,鸡蛋、鱼、豆制品。"
    }
  ],
  "alert": [
    {
      "icon": "🚨",
      "title": "建议骨科评估",
      "content": "医生可能需要 X 光或 MRI 评估关节间隙和软骨。"
    },
    {
      "icon": "🚨",
      "title": "立即就医",
      "content": "若出现关节明显红肿热痛、不能负重、夜间痛加重、关节变形,及时就诊。"
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
