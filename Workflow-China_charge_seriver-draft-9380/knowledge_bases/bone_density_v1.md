---
dataset: questionnaire
questionnaire_id: bone_density_v1
scene: report
tags: [bone_density, screening, report]
updated: 2026-06-17
---

# 骨量减少原因筛查表

为了判断您为什么骨量下降,请填写以下问题。所有题目为单选题,回答没有对错,请根据近 1-2 年的实际情况选择。

## 题目

| id | 题目文本 | 选项 (key: label / weight) | 关联 tag |
|----|----------|----------------------------|----------|
| menopause | 是否已经绝经? | `no: 否/0`, `yes: 是/3` | menopause_related |
| fragility_fracture | 是否有轻微摔倒后骨折史? | `no: 否/0`, `yes: 是/3` | fracture_high_risk |
| family_osteoporosis | 父母是否有髋部骨折或骨质疏松? | `no: 否/0`, `yes: 是/2` | fracture_high_risk |
| sun_exposure | 平时晒太阳是否较少? | `no: 否/0`, `yes: 是/2` | vitamin_d_deficient |
| calcium_intake | 是否很少喝奶、吃豆制品或高钙食物? | `no: 否/0`, `yes: 是/2` | calcium_protein_deficient |
| strength_training | 是否缺乏力量训练或负重运动? | `no: 否/0`, `yes: 是/2` | exercise_deficient |
| low_bmi | 是否体重偏低或近期明显减重? | `no: 否/0`, `yes: 是/1` | calcium_protein_deficient |
| steroid_use | 是否长期服用激素类药物? | `no: 否/0`, `yes: 是/3` | medication_related |
| smoke_alcohol | 是否经常饮酒或吸烟? | `no: 否/0`, `yes: 是/1` | medication_related |
| chronic_disease | 是否有甲状腺、肾病、肝病等问题? | `no: 否/0`, `yes: 是/2` | medication_related |
| spine_symptom | 是否有腰背痛、身高变矮、驼背加重? | `no: 否/0`, `yes: 是/3` | fracture_high_risk |
| vitd_tested | 是否检查过 25-OH 维生素 D? | `no: 否/0`, `low: 是偏低/2`, `normal: 是正常/0` | vitamin_d_deficient |

## 计分与归类规则

- **每个 tag 累计 weight**:
  - `fracture_high_risk` (fragility_fracture + family_osteoporosis + spine_symptom) ≥ 3 → 推荐 `fracture_high_risk` 方案
  - `medication_related` (steroid_use + smoke_alcohol + chronic_disease) ≥ 3 → 推荐 `medication_related` 方案
  - `menopause_related` (menopause=yes) → 推荐 `menopause_related` 方案
  - `vitamin_d_deficient` (sun_exposure + vitd_tested=low) ≥ 2 → 推荐 `vitamin_d_deficient` 方案
  - `calcium_protein_deficient` (calcium_intake + low_bmi) ≥ 2 → 推荐 `calcium_protein_deficient` 方案
  - `exercise_deficient` (strength_training=yes) → 推荐 `exercise_deficient` 方案
- **多 tag 同时命中时优先级**:fracture_high_risk > medication_related > menopause_related > vitamin_d_deficient > calcium_protein_deficient > exercise_deficient
- **riskLevel 映射**:fracture_high_risk/medication_related → high;menopause_related/vitamin_d_deficient → medium;calcium_protein_deficient/exercise_deficient → low

## JSON Schema

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
        { "key": "no", "label": "否", "weight": 0 },
        { "key": "yes", "label": "是", "weight": 3 }
      ],
      "tag": "menopause_related"
    }
  ]
}
```

## 合规提示

- 本量表用于健康初筛与生活方式归类,不能替代医生诊断。
- 任何高风险归类(骨折/药物相关)需提醒"建议尽快就医"。
