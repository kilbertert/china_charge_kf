// DO NOT EDIT - generated from shared/compliance.yaml by scripts/gen_compliance_ts.mjs
// 量表定义 (单一事实源 shared/compliance.yaml)

export type RiskLevel = 'low' | 'medium' | 'high' | 'urgent'

export type QuestionOption = {
  key: string
  label: string
  weight: number
}

export type Question = {
  id: string
  text: string
  type: 'single' | 'multi'
  options: QuestionOption[]
  tag: string
}

export type Questionnaire = {
  id: string
  scene: 'report' | 'symptom' | 'product'
  title: string
  description: string
  questions: Question[]
}

export const BONE_DENSITY_QUESTIONNAIRE: Questionnaire = {
  "id": "bone_density_v1",
  "scene": "report",
  "title": "骨量减少原因筛查表",
  "description": "为了判断您为什么骨量下降,请填写以下问题",
  "questions": [
    {
      "id": "menopause",
      "text": "是否已经绝经?",
      "type": "single",
      "tag": "menopause_related",
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
      ]
    },
    {
      "id": "fragility_fracture",
      "text": "是否有轻微摔倒后骨折史?",
      "type": "single",
      "tag": "fracture_high_risk",
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
      ]
    },
    {
      "id": "family_osteoporosis",
      "text": "父母是否有髋部骨折或骨质疏松?",
      "type": "single",
      "tag": "fracture_high_risk",
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
      ]
    },
    {
      "id": "sun_exposure",
      "text": "平时晒太阳是否较少?",
      "type": "single",
      "tag": "vitamin_d_deficient",
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
      ]
    },
    {
      "id": "calcium_intake",
      "text": "是否很少喝奶、吃豆制品或高钙食物?",
      "type": "single",
      "tag": "calcium_protein_deficient",
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
      ]
    },
    {
      "id": "strength_training",
      "text": "是否缺乏力量训练或负重运动?",
      "type": "single",
      "tag": "exercise_deficient",
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
      ]
    },
    {
      "id": "low_bmi",
      "text": "是否体重偏低或近期明显减重?",
      "type": "single",
      "tag": "calcium_protein_deficient",
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
      ]
    },
    {
      "id": "steroid_use",
      "text": "是否长期服用激素类药物?",
      "type": "single",
      "tag": "medication_related",
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
      ]
    },
    {
      "id": "smoke_alcohol",
      "text": "是否经常饮酒或吸烟?",
      "type": "single",
      "tag": "medication_related",
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
      ]
    },
    {
      "id": "chronic_disease",
      "text": "是否有甲状腺、肾病、肝病等问题?",
      "type": "single",
      "tag": "medication_related",
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
      ]
    },
    {
      "id": "spine_symptom",
      "text": "是否有腰背痛、身高变矮、驼背加重?",
      "type": "single",
      "tag": "fracture_high_risk",
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
      ]
    },
    {
      "id": "vitd_tested",
      "text": "是否检查过 25-OH 维生素 D?",
      "type": "single",
      "tag": "vitamin_d_deficient",
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
      ]
    }
  ]
}

export const LEG_PAIN_QUESTIONNAIRE: Questionnaire = {
  "id": "leg_pain_v1",
  "scene": "symptom",
  "title": "腿疼症状甄别表",
  "description": "先判断危险信号,再定位疼痛特点,最后补充病史",
  "questions": [
    {
      "id": "sudden_severe",
      "text": "腿疼是不是突然发生、并且疼痛很剧烈?",
      "type": "single",
      "tag": "urgent",
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
      ]
    },
    {
      "id": "trauma",
      "text": "最近有没有摔倒、扭伤、撞伤,之后出现腿疼?",
      "type": "single",
      "tag": "urgent",
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
      ]
    },
    {
      "id": "cannot_stand",
      "text": "现在是否不能站立、不能走路或无法负重?",
      "type": "single",
      "tag": "urgent",
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
      ]
    },
    {
      "id": "red_swollen_hot",
      "text": "腿部有没有明显红、肿、热、痛?",
      "type": "single",
      "tag": "urgent",
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
      ]
    },
    {
      "id": "calf_swelling",
      "text": "是否一侧小腿明显肿胀、发紧、发热,按压疼痛?",
      "type": "single",
      "tag": "urgent",
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
      ]
    },
    {
      "id": "chest_discomfort",
      "text": "是否伴有胸闷、胸痛、呼吸困难?",
      "type": "single",
      "tag": "urgent",
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
      ]
    },
    {
      "id": "fever_chills",
      "text": "是否有发热、寒战,或局部皮肤破溃感染?",
      "type": "single",
      "tag": "urgent",
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
      ]
    },
    {
      "id": "location",
      "text": "您主要疼在哪里?",
      "type": "single",
      "tag": "location",
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
      ]
    },
    {
      "id": "side",
      "text": "是一侧疼还是两侧疼?",
      "type": "single",
      "tag": "side",
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
      ]
    },
    {
      "id": "duration",
      "text": "疼痛持续多久了?",
      "type": "single",
      "tag": "duration",
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
      ]
    },
    {
      "id": "trigger",
      "text": "疼痛是怎么出现的?什么情况下更痛?",
      "type": "single",
      "tag": "trigger",
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
      ]
    },
    {
      "id": "quality",
      "text": "疼痛性质更像哪一种?",
      "type": "single",
      "tag": "quality",
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
      ]
    },
    {
      "id": "past_history",
      "text": "是否有腰椎间盘突出、骨质疏松、痛风、糖尿病等病史?",
      "type": "single",
      "tag": "history",
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
      ]
    },
    {
      "id": "lab_abnormal",
      "text": "最近体检是否提示尿酸高、骨密度低、血糖高或炎症指标异常?",
      "type": "single",
      "tag": "history",
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
      ]
    },
    {
      "id": "long_term_meds",
      "text": "是否长期服用激素、抗凝药或其他慢病药物?",
      "type": "single",
      "tag": "history",
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
      ]
    }
  ]
}

export const ALL_QUESTIONNAIRES: Questionnaire[] = [
  BONE_DENSITY_QUESTIONNAIRE,
  LEG_PAIN_QUESTIONNAIRE,
]

export function getQuestionnaireById(id: string): Questionnaire | undefined {
  return ALL_QUESTIONNAIRES.find((q) => q.id === id)
}
