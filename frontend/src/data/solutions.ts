// DO NOT EDIT - generated from shared/compliance.yaml by scripts/gen_compliance_ts.mjs
// 方案模板 (单一事实源 shared/compliance.yaml)

import type { RiskLevel } from './questionnaires'

export type SolutionSection = {
  icon: string
  title: string
  content: string
}

export type Solution = {
  id: string
  scene: 'report' | 'symptom' | 'product'
  tag: string
  title: string
  riskLevel: RiskLevel
  department: string
  oneLineConclusion: string
  lifestyle: SolutionSection[]
  nutrition: SolutionSection[]
  alert: SolutionSection[]
}

export const BONE_DENSITY_SOLUTIONS: Record<string, Solution> = {
  "menopause_related": {
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
  },
  "vitamin_d_deficient": {
    "id": "vitamin_d_deficient_v1",
    "scene": "report",
    "tag": "vitamin_d_deficient",
    "title": "维生素D不足/日晒不足型",
    "riskLevel": "medium",
    "department": "内分泌科",
    "oneLineConclusion": "您的骨量下降与维生素 D 不足高度相关,补 D 是当下最直接可做的事。",
    "lifestyle": [
      {
        "icon": "☀",
        "title": "增加日晒",
        "content": "上午 10 点至下午 3 点,每周 3 次,每次 15-30 分钟裸露前臂。"
      },
      {
        "icon": "🏃",
        "title": "户外活动",
        "content": "把室内运动换成散步、慢跑、园艺,运动和日晒一举两得。"
      }
    ],
    "nutrition": [
      {
        "icon": "🐟",
        "title": "维生素 D",
        "content": "优先食补:三文鱼、沙丁鱼、蛋黄、动物肝脏;不足时按医嘱补充。"
      },
      {
        "icon": "🥛",
        "title": "钙",
        "content": "每日 800-1000mg,维生素 D 不足时钙吸收率会下降。"
      }
    ],
    "alert": [
      {
        "icon": "🚨",
        "title": "建议查血",
        "content": "抽血查 25-OH 维生素 D,目标值 30-50ng/mL。"
      },
      {
        "icon": "⚠",
        "title": "不要自行大剂量补",
        "content": "高剂量维生素 D 长期服用可能中毒,需医生评估后处方。"
      }
    ]
  },
  "calcium_protein_deficient": {
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
  },
  "exercise_deficient": {
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
  },
  "medication_related": {
    "id": "medication_related_v1",
    "scene": "report",
    "tag": "medication_related",
    "title": "药物或慢病相关型",
    "riskLevel": "high",
    "department": "内分泌科 / 相关慢病专科",
    "oneLineConclusion": "您的骨量下降与长期用药或慢性病相关,需要专科医生综合评估治疗方案。",
    "lifestyle": [
      {
        "icon": "📋",
        "title": "记录用药史",
        "content": "把长期用药清单带给医生,评估药物对骨代谢的影响。"
      },
      {
        "icon": "🛡",
        "title": "防跌倒",
        "content": "药物可能影响平衡能力,尤其夜间起夜注意安全。"
      }
    ],
    "nutrition": [
      {
        "icon": "🥛",
        "title": "钙",
        "content": "每日 800-1000mg,与药物服用时间错开 2 小时。"
      },
      {
        "icon": "🐟",
        "title": "维生素 D",
        "content": "与医生确认补充剂量,部分慢病患者需要更高剂量。"
      }
    ],
    "alert": [
      {
        "icon": "🚨",
        "title": "不要自行停药",
        "content": "激素、抗凝药等是治疗原发病的关键,停药风险远大于骨质疏松。"
      },
      {
        "icon": "🚨",
        "title": "建议多学科会诊",
        "content": "原发病专科 + 骨质疏松门诊共同制定方案。"
      }
    ]
  },
  "fracture_high_risk": {
    "id": "fracture_high_risk_v1",
    "scene": "report",
    "tag": "fracture_high_risk",
    "title": "骨折高风险型",
    "riskLevel": "high",
    "department": "骨科 / 骨质疏松门诊",
    "oneLineConclusion": "您存在多项骨折高风险因素,需要尽快评估是否启动抗骨松药物治疗。",
    "lifestyle": [
      {
        "icon": "🛡",
        "title": "重点防跌倒",
        "content": "家中加装扶手、防滑垫、感应灯;外出穿防滑鞋。"
      },
      {
        "icon": "🚶",
        "title": "避免高风险动作",
        "content": "不搬重物、不弯腰提物、不做突然扭转。"
      }
    ],
    "nutrition": [
      {
        "icon": "🥛",
        "title": "钙",
        "content": "每日 1000-1200mg,饮食+补充剂。"
      },
      {
        "icon": "🐟",
        "title": "维生素 D",
        "content": "维持 25-OH D 在 30ng/mL 以上。"
      }
    ],
    "alert": [
      {
        "icon": "🚨",
        "title": "尽快就医",
        "content": "建议在 1 个月内到骨质疏松门诊或骨科评估,询问是否需要双膦酸盐、地舒单抗等治疗。"
      },
      {
        "icon": "🚨",
        "title": "紧急就医",
        "content": "若出现身高变矮明显、腰背剧痛或轻微摔倒后疼痛,立即就诊排除骨折。"
      }
    ]
  }
}

export const LEG_PAIN_SOLUTIONS: Record<string, Solution> = {
  "urgent": {
    "id": "urgent_v1",
    "scene": "symptom",
    "tag": "urgent",
    "title": "紧急症状 - 需立即就医",
    "riskLevel": "urgent",
    "department": "急诊 / 血管外科 / 骨科",
    "oneLineConclusion": "您的症状可能提示需要紧急评估,请优先就医,不要拖延。",
    "lifestyle": [],
    "nutrition": [],
    "alert": [
      {
        "icon": "🚨",
        "title": "尽快就医",
        "content": "出现一侧小腿肿胀+胸闷气短,警惕肺栓塞;胸痛/呼吸困难/不能站立等危险信号请立即急诊或对应专科。"
      },
      {
        "icon": "🚑",
        "title": "呼叫帮助",
        "content": "如症状突发且剧烈,请拨打 120 或由家属陪同就近急诊,避免自行驾车。"
      }
    ]
  },
  "muscle_strain": {
    "id": "muscle_strain_v1",
    "scene": "symptom",
    "tag": "muscle_strain",
    "title": "肌肉劳损/运动过度型",
    "riskLevel": "low",
    "department": "康复科 / 骨科",
    "oneLineConclusion": "您的情况更像是肌肉劳损或运动后疲劳相关,建议就医明确诊断后再制定方案。",
    "lifestyle": [],
    "nutrition": [],
    "alert": [
      {
        "icon": "💡",
        "title": "观察 1-2 周",
        "content": "如疼痛不减轻或加重,需重新评估。"
      }
    ]
  },
  "knee_degeneration": {
    "id": "knee_degeneration_v1",
    "scene": "symptom",
    "tag": "knee_degeneration",
    "title": "膝关节/关节退变型",
    "riskLevel": "medium",
    "department": "骨科 / 康复科",
    "oneLineConclusion": "您的情况更像是膝关节负重或退变相关,建议骨科评估明确诊断后再制定方案。",
    "lifestyle": [],
    "nutrition": [],
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
  },
  "lumbar_radiculopathy": {
    "id": "lumbar_radiculopathy_v1",
    "scene": "symptom",
    "tag": "lumbar_radiculopathy",
    "title": "腰椎神经牵涉型",
    "riskLevel": "medium",
    "department": "骨科 / 脊柱外科 / 康复科",
    "oneLineConclusion": "您的情况更像是腰椎相关神经受刺激,建议脊柱外科明确诊断后再制定方案。",
    "lifestyle": [],
    "nutrition": [],
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
  },
  "gout_inflammatory": {
    "id": "gout_inflammatory_v1",
    "scene": "symptom",
    "tag": "gout_inflammatory",
    "title": "尿酸/痛风炎症型",
    "riskLevel": "medium",
    "department": "风湿免疫科 / 骨科",
    "oneLineConclusion": "您的情况可能与尿酸相关关节炎症有关,建议风湿免疫科评估并明确是否需要降尿酸治疗。",
    "lifestyle": [],
    "nutrition": [],
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
  },
  "vascular_risk": {
    "id": "vascular_risk_v1",
    "scene": "symptom",
    "tag": "vascular_risk",
    "title": "血管循环风险型",
    "riskLevel": "high",
    "department": "血管外科 / 急诊",
    "oneLineConclusion": "您的情况可能与血管相关风险有关,需要优先排除血栓和循环问题,不能拖延。",
    "lifestyle": [],
    "nutrition": [],
    "alert": [
      {
        "icon": "🚨",
        "title": "尽快就医",
        "content": "一侧小腿肿胀 + 胸闷气短需紧急排查肺栓塞;单纯小腿肿胀需排查深静脉血栓。"
      },
      {
        "icon": "🚨",
        "title": "急诊指征",
        "content": "突然胸痛、咯血、晕厥 -> 立即急诊(120)。"
      },
      {
        "icon": "⚠",
        "title": "就医前注意",
        "content": "小腿肿胀期间不要按摩或热敷,以免血栓脱落;避免久坐久卧,长途旅行每 1-2 小时起身活动。"
      }
    ]
  },
  "osteoporosis_risk": {
    "id": "osteoporosis_risk_v1",
    "scene": "symptom",
    "tag": "osteoporosis_risk",
    "title": "骨质疏松/骨折风险型",
    "riskLevel": "high",
    "department": "骨科 / 骨质疏松门诊",
    "oneLineConclusion": "您的情况可能与骨质疏松或隐匿骨折相关,需要影像学确认和骨密度评估。",
    "lifestyle": [],
    "nutrition": [],
    "alert": [
      {
        "icon": "🚨",
        "title": "建议就医",
        "content": "骨科或骨质疏松门诊,可能需要 X 光和 DXA 骨密度检查。"
      },
      {
        "icon": "🚨",
        "title": "紧急就医",
        "content": "轻微外伤后明显疼痛、身高变矮、腰背剧痛,需立即排查骨折。"
      }
    ]
  }
}

export function getSolution(scene: 'report' | 'symptom', tag: string): Solution | undefined {
  if (scene === 'report') return BONE_DENSITY_SOLUTIONS[tag]
  if (scene === 'symptom') return LEG_PAIN_SOLUTIONS[tag]
  return undefined
}

export function listSolutions(scene: 'report' | 'symptom'): Solution[] {
  if (scene === 'report') return Object.values(BONE_DENSITY_SOLUTIONS)
  if (scene === 'symptom') return Object.values(LEG_PAIN_SOLUTIONS)
  return []
}
