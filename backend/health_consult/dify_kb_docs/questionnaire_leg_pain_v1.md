---
category: questionnaire
doc_id: leg_pain_v1
title: 腿疼症状甄别表
---

# 腿疼症状甄别表

> 本文档为 Dify 知识库 (dataset: questionnaire) 条目。LLM 在场景识别后可由 `knowledge-retrieval` 节点按 `doc_id` 或 `tag` 检索,前端可走硬编码 fallback。

## 字段结构

```json
{
  "id": "leg_pain_v1",
  "scene": "symptom",
  "title": "腿疼症状甄别表",
  "description": "先判断危险信号,再定位疼痛特点,最后补充病史",
  "questions": [
    {
      "id": "sudden_severe",
      "text": "腿疼是不是突然发生、并且疼痛很剧烈?",
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
      "tag": "urgent"
    },
    {
      "id": "trauma",
      "text": "最近有没有摔倒、扭伤、撞伤,之后出现腿疼?",
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
      "tag": "urgent"
    },
    {
      "id": "cannot_stand",
      "text": "现在是否不能站立、不能走路或无法负重?",
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
      "tag": "urgent"
    },
    {
      "id": "red_swollen_hot",
      "text": "腿部有没有明显红、肿、热、痛?",
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
      "tag": "urgent"
    },
    {
      "id": "calf_swelling",
      "text": "是否一侧小腿明显肿胀、发紧、发热,按压疼痛?",
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
      "tag": "urgent"
    },
    {
      "id": "chest_discomfort",
      "text": "是否伴有胸闷、胸痛、呼吸困难?",
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
      "tag": "urgent"
    },
    {
      "id": "fever_chills",
      "text": "是否有发热、寒战,或局部皮肤破溃感染?",
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
      "tag": "urgent"
    },
    {
      "id": "location",
      "text": "您主要疼在哪里?",
      "type": "single",
      "options": [
        {
          "key": "hip",
          "label": "髋部/大腿根",
          "weight": 0
        },
        {
          "key": "thigh_front",
          "label": "大腿前侧",
          "weight": 0
        },
        {
          "key": "thigh_back",
          "label": "大腿后侧",
          "weight": 0
        },
        {
          "key": "knee",
          "label": "膝盖",
          "weight": 0
        },
        {
          "key": "calf",
          "label": "小腿",
          "weight": 0
        },
        {
          "key": "ankle_heel",
          "label": "脚踝/足跟",
          "weight": 0
        },
        {
          "key": "radiating",
          "label": "整条腿放射样疼痛",
          "weight": 0
        }
      ],
      "tag": "location"
    },
    {
      "id": "side",
      "text": "是一侧疼还是两侧疼?",
      "type": "single",
      "options": [
        {
          "key": "one_side",
          "label": "一侧",
          "weight": 0
        },
        {
          "key": "both",
          "label": "两侧",
          "weight": 0
        },
        {
          "key": "unsure",
          "label": "不确定",
          "weight": 0
        }
      ],
      "tag": "side"
    },
    {
      "id": "duration",
      "text": "疼痛持续多久了?",
      "type": "single",
      "options": [
        {
          "key": "lt_1d",
          "label": "1天以内",
          "weight": 0
        },
        {
          "key": "d_2_7",
          "label": "2-7天",
          "weight": 0
        },
        {
          "key": "w_1_4",
          "label": "1-4周",
          "weight": 0
        },
        {
          "key": "gt_1m",
          "label": "超过1个月",
          "weight": 0
        },
        {
          "key": "recurrent",
          "label": "反复发作",
          "weight": 0
        }
      ],
      "tag": "duration"
    },
    {
      "id": "trigger",
      "text": "疼痛是怎么出现的?什么情况下更痛?",
      "type": "single",
      "options": [
        {
          "key": "after_exercise",
          "label": "运动后出现",
          "weight": 0
        },
        {
          "key": "after_sit_stand",
          "label": "久坐久站后出现",
          "weight": 0
        },
        {
          "key": "stairs",
          "label": "走路上下楼明显",
          "weight": 0
        },
        {
          "key": "night_rest",
          "label": "夜间或休息时明显",
          "weight": 0
        },
        {
          "key": "no_cause",
          "label": "没有明显诱因",
          "weight": 0
        }
      ],
      "tag": "trigger"
    },
    {
      "id": "quality",
      "text": "疼痛性质更像哪一种?",
      "type": "single",
      "options": [
        {
          "key": "ache",
          "label": "酸痛",
          "weight": 0
        },
        {
          "key": "distending",
          "label": "胀痛",
          "weight": 0
        },
        {
          "key": "stabbing",
          "label": "刺痛",
          "weight": 0
        },
        {
          "key": "burning",
          "label": "灼痛",
          "weight": 0
        },
        {
          "key": "numb",
          "label": "麻痛",
          "weight": 0
        },
        {
          "key": "cramp",
          "label": "抽筋样疼",
          "weight": 0
        },
        {
          "key": "deep_joint",
          "label": "关节深处痛",
          "weight": 0
        }
      ],
      "tag": "quality"
    },
    {
      "id": "past_history",
      "text": "是否有腰椎间盘突出、骨质疏松、痛风、糖尿病等病史?",
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
          "weight": 0
        },
        {
          "key": "unsure",
          "label": "不清楚",
          "weight": 0
        }
      ],
      "tag": "history"
    },
    {
      "id": "lab_abnormal",
      "text": "最近体检是否提示尿酸高、骨密度低、血糖高或炎症指标异常?",
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
          "weight": 0
        },
        {
          "key": "unsure",
          "label": "不清楚",
          "weight": 0
        }
      ],
      "tag": "history"
    },
    {
      "id": "long_term_meds",
      "text": "是否长期服用激素、抗凝药或其他慢病药物?",
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
          "weight": 0
        },
        {
          "key": "unsure",
          "label": "不清楚",
          "weight": 0
        }
      ],
      "tag": "history"
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
