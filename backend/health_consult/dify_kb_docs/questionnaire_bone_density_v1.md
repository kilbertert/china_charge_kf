---
category: questionnaire
doc_id: bone_density_v1
title: 骨量减少原因筛查表
---

# 骨量减少原因筛查表

> 本文档为 Dify 知识库 (dataset: questionnaire) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "bone_density_v1",
  "scene": "report",
  "title": "骨量减少原因筛查表",
  "description": "为了判断您为什么骨量下降,请填写以下问题",
  "questions": [
    {
      "id": "menopause",
      "text": "是否已经绝经?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 3
        }
      ],
      "tag": "menopause_related"
    },
    {
      "id": "fragility_fracture",
      "text": "是否有轻微摔倒后骨折史?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 3
        }
      ],
      "tag": "fracture_high_risk"
    },
    {
      "id": "family_osteoporosis",
      "text": "父母是否有髋部骨折或骨质疏松?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 2
        }
      ],
      "tag": "fracture_high_risk"
    },
    {
      "id": "sun_exposure",
      "text": "平时晒太阳是否较少?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 2
        }
      ],
      "tag": "vitamin_d_deficient"
    },
    {
      "id": "calcium_intake",
      "text": "是否很少喝奶、吃豆制品或高钙食物?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 2
        }
      ],
      "tag": "calcium_protein_deficient"
    },
    {
      "id": "strength_training",
      "text": "是否缺乏力量训练或负重运动?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 2
        }
      ],
      "tag": "exercise_deficient"
    },
    {
      "id": "low_bmi",
      "text": "是否体重偏低或近期明显减重?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 1
        }
      ],
      "tag": "calcium_protein_deficient"
    },
    {
      "id": "steroid_use",
      "text": "是否长期服用激素类药物?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 3
        }
      ],
      "tag": "medication_related"
    },
    {
      "id": "smoke_alcohol",
      "text": "是否经常饮酒或吸烟?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 1
        }
      ],
      "tag": "medication_related"
    },
    {
      "id": "chronic_disease",
      "text": "是否有甲状腺、肾病、肝病等问题?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 2
        }
      ],
      "tag": "medication_related"
    },
    {
      "id": "spine_symptom",
      "text": "是否有腰背痛、身高变矮、驼背加重?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "yes",
          "label": "是",
          "weight": 3
        }
      ],
      "tag": "fracture_high_risk"
    },
    {
      "id": "vitd_tested",
      "text": "是否检查过 25-OH 维生素 D?",
      "type": "single",
      "options": [
        {
          "key": "no",
          "label": "否",
          "weight": 0
        },
        {
          "key": "low",
          "label": "是,结果偏低",
          "weight": 2
        },
        {
          "key": "normal",
          "label": "是,结果正常",
          "weight": 0
        }
      ],
      "tag": "vitamin_d_deficient"
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
