---
dataset: questionnaire
questionnaire_id: leg_pain_v1
scene: symptom
tags: [leg_pain, danger_signal, screening]
updated: 2026-06-17
---

# 腿疼症状甄别表

先判断危险信号,再定位疼痛特点,最后补充病史。共 15 题,分 A/B/C 三组。

## A 组:危险信号(7 题,任意 "是" → urgent)

| id | 题目文本 | 选项 (key: label / weight) | 关联 tag |
|----|----------|----------------------------|----------|
| sudden_severe | 腿疼是不是突然发生、并且疼痛很剧烈? | `no: 否/0`, `yes: 是/3` | urgent |
| trauma | 最近有没有摔倒、扭伤、撞伤,之后出现腿疼? | `no: 否/0`, `yes: 是/3` | urgent |
| cannot_stand | 现在是否不能站立、不能走路或无法负重? | `no: 否/0`, `yes: 是/3` | urgent |
| red_swollen_hot | 腿部有没有明显红、肿、热、痛? | `no: 否/0`, `yes: 是/2` | urgent |
| calf_swelling | 是否一侧小腿明显肿胀、发紧、发热,按压疼痛? | `no: 否/0`, `yes: 是/3` | urgent |
| chest_discomfort | 是否伴有胸闷、胸痛、呼吸困难? | `no: 否/0`, `yes: 是/3` | urgent |
| fever_chills | 是否有发热、寒战,或局部皮肤破溃感染? | `no: 否/0`, `yes: 是/2` | urgent |

**A 组规则**:任意一题回答 `yes` → 立即标记 `risk_level=urgent`,跳过 B/C 组,直接出紧急建议(血管/神经/感染排查)。

## B 组:定位量表(5 题)

| id | 题目文本 | 选项 (key: label) | 关联 tag |
|----|----------|-------------------|----------|
| location | 您主要疼在哪里? | `hip: 髋部/大腿根`, `thigh_front: 大腿前侧`, `thigh_back: 大腿后侧`, `knee: 膝盖`, `calf: 小腿`, `ankle_heel: 脚踝/足跟`, `radiating: 整条腿放射样疼痛` | location |
| side | 是一侧疼还是两侧疼? | `one_side: 一侧`, `both: 两侧`, `unsure: 不确定` | side |
| duration | 疼痛持续多久了? | `lt_1d: 1天以内`, `d_2_7: 2-7天`, `w_1_4: 1-4周`, `gt_1m: 超过1个月`, `recurrent: 反复发作` | duration |
| trigger | 疼痛是怎么出现的?什么情况下更痛? | `after_exercise: 运动后`, `after_sit_stand: 久坐久站后`, `stairs: 走路上下楼明显`, `night_rest: 夜间或休息时`, `no_cause: 没有明显诱因` | trigger |
| quality | 疼痛性质更像哪一种? | `ache: 酸痛`, `distending: 胀痛`, `stabbing: 刺痛`, `burning: 灼痛`, `numb: 麻痛`, `cramp: 抽筋样`, `deep_joint: 关节深处痛` | quality |

## C 组:伴随症状与病史(3 题)

| id | 题目文本 | 选项 (key: label) | 关联 tag |
|----|----------|-------------------|----------|
| past_history | 是否有腰椎间盘突出、骨质疏松、痛风、糖尿病等病史? | `no: 否`, `yes: 是`, `unsure: 不清楚` | history |
| lab_abnormal | 最近体检是否提示尿酸高、骨密度低、血糖高或炎症指标异常? | `no: 否`, `yes: 是`, `unsure: 不清楚` | history |
| long_term_meds | 是否长期服用激素、抗凝药或其他慢病药物? | `no: 否`, `yes: 是`, `unsure: 不清楚` | history |

## 答案归类规则(B+C 组,无危险信号时)

| 条件 | 推荐 tag | riskLevel |
|------|----------|-----------|
| `location=knee` 或 `trigger=stairs` | `knee_degeneration` | medium |
| `location ∈ {thigh_back, radiating}` 或 `past_history=yes` | `lumbar_radiculopathy` | medium |
| `location=calf` 或 A 组 calf_swelling=yes(若已 urgent 则不归这里) | `vascular_risk` | high |
| `lab_abnormal=yes` 且 `past_history=yes` | `gout_inflammatory` | medium |
| `duration=gt_1m` 或 `fragility_fracture=yes`(仅当未触发 urgent) | `osteoporosis_risk` | high |
| 兜底 | `muscle_strain` | low |

## JSON Schema

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
        { "key": "no", "label": "否", "weight": 0 },
        { "key": "yes", "label": "是", "weight": 3 }
      ],
      "tag": "urgent"
    }
  ]
}
```

## 合规提示

- A 组任一题命中 → 必出"立即就医/急诊"提示,不得输出生活方式建议。
- B/C 组输出必须含"建议咨询医生/不能替代诊断"措辞。
- 字段 `solutionRef` 用于前端拉方案:`knee_degeneration_v1` / `lumbar_radiculopathy_v1` / `vascular_risk_v1` / `gout_inflammatory_v1` / `osteoporosis_risk_v1` / `muscle_strain_v1`。
