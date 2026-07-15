// 共享 JSON 契约:量表定义
// 来源:AI健康咨询模块场景GPT对话1.docx (P454-465 骨密度 12 题, P551-581 腿疼危险信号 7 题,
//       P613-650 腿疼定位 4 题, P1336-1348 腿疼病史 3 题)
// Dify / 后端 / 前端三方共用,Dify 端用 knowledge-retrieval 拉取,前端硬编码 fallback。

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

// ─── 骨密度 12 题 ──────────────────────────────────────────────
export const BONE_DENSITY_QUESTIONNAIRE: Questionnaire = {
  id: 'bone_density_v1',
  scene: 'report',
  title: '骨量减少原因筛查表',
  description: '为了判断您为什么骨量下降,请填写以下问题',
  questions: [
    {
      id: 'menopause',
      text: '是否已经绝经?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'menopause_related',
    },
    {
      id: 'fragility_fracture',
      text: '是否有轻微摔倒后骨折史?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'fracture_high_risk',
    },
    {
      id: 'family_osteoporosis',
      text: '父母是否有髋部骨折或骨质疏松?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 2 },
      ],
      tag: 'fracture_high_risk',
    },
    {
      id: 'sun_exposure',
      text: '平时晒太阳是否较少?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 2 },
      ],
      tag: 'vitamin_d_deficient',
    },
    {
      id: 'calcium_intake',
      text: '是否很少喝奶、吃豆制品或高钙食物?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 2 },
      ],
      tag: 'calcium_protein_deficient',
    },
    {
      id: 'strength_training',
      text: '是否缺乏力量训练或负重运动?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 2 },
      ],
      tag: 'exercise_deficient',
    },
    {
      id: 'low_bmi',
      text: '是否体重偏低或近期明显减重?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 1 },
      ],
      tag: 'calcium_protein_deficient',
    },
    {
      id: 'steroid_use',
      text: '是否长期服用激素类药物?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'medication_related',
    },
    {
      id: 'smoke_alcohol',
      text: '是否经常饮酒或吸烟?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 1 },
      ],
      tag: 'medication_related',
    },
    {
      id: 'chronic_disease',
      text: '是否有甲状腺、肾病、肝病等问题?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 2 },
      ],
      tag: 'medication_related',
    },
    {
      id: 'spine_symptom',
      text: '是否有腰背痛、身高变矮、驼背加重?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'fracture_high_risk',
    },
    {
      id: 'vitd_tested',
      text: '是否检查过 25-OH 维生素 D?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'low', label: '是,结果偏低', weight: 2 },
        { key: 'normal', label: '是,结果正常', weight: 0 },
      ],
      tag: 'vitamin_d_deficient',
    },
  ],
}

// ─── 腿疼 A+B+C 三表,questions 顺序按 A→B→C ────────────────
export const LEG_PAIN_QUESTIONNAIRE: Questionnaire = {
  id: 'leg_pain_v1',
  scene: 'symptom',
  title: '腿疼症状甄别表',
  description: '先判断危险信号,再定位疼痛特点,最后补充病史',
  questions: [
    // A 表:危险信号 7 题(P551-581)
    {
      id: 'sudden_severe',
      text: '腿疼是不是突然发生、并且疼痛很剧烈?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'urgent',
    },
    {
      id: 'trauma',
      text: '最近有没有摔倒、扭伤、撞伤,之后出现腿疼?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'urgent',
    },
    {
      id: 'cannot_stand',
      text: '现在是否不能站立、不能走路或无法负重?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'urgent',
    },
    {
      id: 'red_swollen_hot',
      text: '腿部有没有明显红、肿、热、痛?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 2 },
      ],
      tag: 'urgent',
    },
    {
      id: 'calf_swelling',
      text: '是否一侧小腿明显肿胀、发紧、发热,按压疼痛?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'urgent',
    },
    {
      id: 'chest_discomfort',
      text: '是否伴有胸闷、胸痛、呼吸困难?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 3 },
      ],
      tag: 'urgent',
    },
    {
      id: 'fever_chills',
      text: '是否有发热、寒战,或局部皮肤破溃感染?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 2 },
      ],
      tag: 'urgent',
    },
    // B 表:定位量表 4 题(P613-650)
    {
      id: 'location',
      text: '您主要疼在哪里?',
      type: 'single',
      options: [
        { key: 'hip', label: '髋部/大腿根', weight: 0 },
        { key: 'thigh_front', label: '大腿前侧', weight: 0 },
        { key: 'thigh_back', label: '大腿后侧', weight: 0 },
        { key: 'knee', label: '膝盖', weight: 0 },
        { key: 'calf', label: '小腿', weight: 0 },
        { key: 'ankle_heel', label: '脚踝/足跟', weight: 0 },
        { key: 'radiating', label: '整条腿放射样疼痛', weight: 0 },
      ],
      tag: 'location',
    },
    {
      id: 'side',
      text: '是一侧疼还是两侧疼?',
      type: 'single',
      options: [
        { key: 'one_side', label: '一侧', weight: 0 },
        { key: 'both', label: '两侧', weight: 0 },
        { key: 'unsure', label: '不确定', weight: 0 },
      ],
      tag: 'side',
    },
    {
      id: 'duration',
      text: '疼痛持续多久了?',
      type: 'single',
      options: [
        { key: 'lt_1d', label: '1天以内', weight: 0 },
        { key: 'd_2_7', label: '2-7天', weight: 0 },
        { key: 'w_1_4', label: '1-4周', weight: 0 },
        { key: 'gt_1m', label: '超过1个月', weight: 0 },
        { key: 'recurrent', label: '反复发作', weight: 0 },
      ],
      tag: 'duration',
    },
    {
      id: 'trigger',
      text: '疼痛是怎么出现的?什么情况下更痛?',
      type: 'single',
      options: [
        { key: 'after_exercise', label: '运动后出现', weight: 0 },
        { key: 'after_sit_stand', label: '久坐久站后出现', weight: 0 },
        { key: 'stairs', label: '走路上下楼明显', weight: 0 },
        { key: 'night_rest', label: '夜间或休息时明显', weight: 0 },
        { key: 'no_cause', label: '没有明显诱因', weight: 0 },
      ],
      tag: 'trigger',
    },
    {
      id: 'quality',
      text: '疼痛性质更像哪一种?',
      type: 'single',
      options: [
        { key: 'ache', label: '酸痛', weight: 0 },
        { key: 'distending', label: '胀痛', weight: 0 },
        { key: 'stabbing', label: '刺痛', weight: 0 },
        { key: 'burning', label: '灼痛', weight: 0 },
        { key: 'numb', label: '麻痛', weight: 0 },
        { key: 'cramp', label: '抽筋样疼', weight: 0 },
        { key: 'deep_joint', label: '关节深处痛', weight: 0 },
      ],
      tag: 'quality',
    },
    // C 表:伴随症状与病史 3 题(P1336-1348)
    {
      id: 'past_history',
      text: '是否有腰椎间盘突出、骨质疏松、痛风、糖尿病等病史?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 0 },
        { key: 'unsure', label: '不清楚', weight: 0 },
      ],
      tag: 'history',
    },
    {
      id: 'lab_abnormal',
      text: '最近体检是否提示尿酸高、骨密度低、血糖高或炎症指标异常?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 0 },
        { key: 'unsure', label: '不清楚', weight: 0 },
      ],
      tag: 'history',
    },
    {
      id: 'long_term_meds',
      text: '是否长期服用激素、抗凝药或其他慢病药物?',
      type: 'single',
      options: [
        { key: 'no', label: '否', weight: 0 },
        { key: 'yes', label: '是', weight: 0 },
        { key: 'unsure', label: '不清楚', weight: 0 },
      ],
      tag: 'history',
    },
  ],
}

export const ALL_QUESTIONNAIRES: Questionnaire[] = [
  BONE_DENSITY_QUESTIONNAIRE,
  LEG_PAIN_QUESTIONNAIRE,
]

export function getQuestionnaireById(id: string): Questionnaire | undefined {
  return ALL_QUESTIONNAIRES.find((q) => q.id === id)
}
