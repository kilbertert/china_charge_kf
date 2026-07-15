# AI 健康咨询模块 - 知识库设计

本文档说明 `AI_health_consultant_v2` 工作流所需的 3 个 Dify 知识库。文件命名、frontmatter 模板、上传顺序均按 Dify 控制台最佳实践。

> 部署到 Dify 后,需要把工作流 yml 里的占位符 `<DATASET_PRODUCT>` / `<DATASET_QUESTIONNAIRE>` / `<DATASET_SOLUTION>` 替换成真实的 dataset_id。

---

## 1. 产品库 (Product KB)

**dataset_id 候选**:
- 复用现有 `cJ687vaaJbsFc7MghKK/6gS+0+mJHna8xcsp3EgZpz4FTn6Z2PZ8MtU8c36SDHxB`(原 workflow 已在用,内容可能需补)
- 或新建空库,上传以下 markdown 后获取新 id

**用途**:场景三(产品问答)用 RAG 检索匹配产品成分、适用人群、注意事项

**文档格式**:每个产品一个 markdown 文件,文件名按产品 ID,例如 `calcium_carbonate_d3.md`

**frontmatter 模板**:
```yaml
---
dataset: product
product_id: <string>
product_name: <string>
product_type: 普通食品 | 保健食品 | 营养补充剂
tags: [成分, 人群, ...]
scene: product
updated: 2026-06-17
---

# <产品中文名>(<英文名>)

## 产品类型
- 分类:保健食品(蓝帽子) / 普通食品 / 营养补充剂
- 主要成分:...
- 含量:每片 / 每袋 / 每日剂量

## 适合人群
- <场景 1>:如中老年女性补钙、绝经后骨量减少
- <场景 2>:...

## 不适合人群
- 婴幼儿 / 孕妇 / 哺乳期 / 慢性病人群 / 服药人群等

## 注意事项
- 与药物服用时间错开 2 小时
- 不能替代药物、不能治疗疾病
- 过敏原提示

## 常见问题
### Q1: <常见问题>
A: <基于产品事实的客观回答,避免疗效承诺>

### Q2: ...
```

**MVP 上传建议**:至少 1 个示范产品(钙片 + 维生素 D3) 用于冒烟测试,后续按销售小程序 SKU 列表批量补充。

---

## 2. 量表库 (Questionnaire KB)

**dataset_id**:新建。`frontend/src/data/questionnaires.ts` 中所有量表 JSON 以 markdown 代码块嵌入

**用途**:场景二(腿疼) 首屏输出量表,前端可硬编码 fallback,Dify 端用 RAG 检索

**文档清单**(本目录已生成):
| 文件 | 场景 | 题数 | 用途 |
|------|------|------|------|
| `bone_density_v1.md` | report | 12 | 骨量减少原因筛查(场景一 屏 3) |
| `leg_pain_v1.md` | symptom | 15 (7 危险 + 5 定位 + 3 病史) | 腿疼症状甄别(场景二 屏 3) |

**frontmatter 模板**:
```yaml
---
dataset: questionnaire
questionnaire_id: <bone_density_v1 | leg_pain_v1>
scene: report | symptom
tags: [bone_density, screening]  # 用于 RAG 召回
updated: 2026-06-17
---

# <量表标题>

<量表描述>

## 题目

| id | 题目 | 选项 keys | weight | tag |
|----|------|-----------|--------|-----|
| ... | ... | no/yes | 0/3 | ... |

## 计分规则
- 各 tag 累计 weight ≥ N → 推荐该方案

## JSON Schema
```json
{
  "id": "...",
  "questions": [...]
}
```
```

---

## 3. 方案库 (Solution KB)

**dataset_id**:新建。`frontend/src/data/solutions.ts` 中 12 个方案以独立 markdown 嵌入

**用途**:场景一/二 答案归类后检索匹配方案,前端可硬编码 fallback

**文档清单**(本目录已生成,`solutions/<tag>.md`):
| tag | scene | riskLevel | department | 用途 |
|-----|-------|-----------|------------|------|
| `menopause_related` | report | medium | 内分泌科 | 年龄/绝经相关骨量流失 |
| `vitamin_d_deficient` | report | medium | 内分泌科 | 维生素 D 不足 |
| `calcium_protein_deficient` | report | low | 营养科 | 钙和蛋白摄入不足 |
| `exercise_deficient` | report | low | 康复科 | 缺乏运动 |
| `medication_related` | report | high | 内分泌科 | 药物/慢病相关 |
| `fracture_high_risk` | report | high | 骨科 | 骨折高风险 |
| `muscle_strain` | symptom | low | 康复科 | 肌肉劳损 |
| `knee_degeneration` | symptom | medium | 骨科 | 膝关节退变 |
| `lumbar_radiculopathy` | symptom | medium | 骨科 | 腰椎神经牵涉 |
| `gout_inflammatory` | symptom | medium | 风湿免疫科 | 尿酸/痛风 |
| `vascular_risk` | symptom | high | 血管外科 | 血管循环风险 |
| `osteoporosis_risk` | symptom | high | 骨科 | 骨质疏松/骨折风险 |

**frontmatter 模板**:
```yaml
---
dataset: solution
solution_id: <tag>_v1
tag: <tag>
scene: report | symptom
risk_level: low | medium | high | urgent
department: <科室>
updated: 2026-06-17
---

# <方案标题>

## 一句话结论
<oneLineConclusion>

## 生活方式建议
- <icon> <title>: <content>
- ...

## 营养建议
- <icon> <title>: <content>
- ...

## 警示与就医
- <icon> <title>: <content>
- ...

## JSON
```json
{
  "id": "...",
  "tag": "...",
  "lifestyle": [...],
  "nutrition": [...],
  "alert": [...]
}
```
```

---

## 部署顺序

1. **先建产品库**(若用现有 dataset_id 可跳过)
2. **再建量表库**:上传 `bone_density_v1.md` + `leg_pain_v1.md`,获取 dataset_id → 替换 yml `<DATASET_QUESTIONNAIRE>`
3. **再建方案库**:上传 12 个 `solutions/*.md`,获取 dataset_id → 替换 yml `<DATASET_SOLUTION>`
4. **导入工作流 yml**:在 Dify 控制台 "导入应用 DSL" → 上传 `AI_health_consultant_v2.yml` → 检查所有节点 dataset_ids 已替换
5. **发布 + 测 3 个用例**(骨密度 / 腿疼无危险 / 腿疼危险信号)

详细步骤见同目录 `DEPLOY_INSTRUCTIONS.md`。
