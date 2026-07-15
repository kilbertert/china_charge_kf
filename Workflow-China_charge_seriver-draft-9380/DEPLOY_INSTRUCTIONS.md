# 部署说明 - AI_health_consultant_v2

> 给 Agent 4(集成与部署工程师)使用。本文档说明如何在 Dify 控制台完成 `AI_health_consultant_v2.yml` + 3 个知识库的上线和验证。

**前置条件**:
- 服务器 `124.243.178.156` 上 Dify 已部署(原 workflow_id `7615498037791588402`)
- 已有 Dify 控制台管理员账号
- `Workflow-China_charge_seriver-draft-9380/` 目录已同步到 `/root/dify/china_charge_kf/`

---

## 步骤 1: 同步文件到服务器

```bash
rsync -avz "d:/AI/company-projects/ai-customer/china_charge_kf/Workflow-China_charge_seriver-draft-9380/" \
  root@124.243.178.156:/root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/
```

确认文件:
```bash
ssh root@124.243.178.156 "ls -la /root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/knowledge_bases/solutions/"
# 期望 12 个 .md 文件
```

---

## 步骤 2: 创建产品库(场景三用)

**选项 A — 复用现有 dataset**:
- 直接使用 `cJ687vaaJbsFc7MghKK/6gS+0+mJHna8xcsp3EgZpz4FTn6Z2PZ8MtU8c36SDHxB`
- 跳过新建

**选项 B — 新建**:
1. Dify 控制台 → 知识库 → 创建知识库
2. 名称:`china-charge-product`
3. 索引模式:高质量(已有 rerank 模型)
4. 跳过上传文档(等 MVP 上线后按销售 SKU 补),本步骤不阻塞工作流导入

**记录 dataset_id**:
```
DIFY_DATASET_PRODUCT = <从控制台 URL 复制>
```

---

## 步骤 3: 创建量表库

1. Dify 控制台 → 知识库 → 创建知识库
2. 名称:`china-charge-questionnaire`
3. 索引模式:高质量
4. 上传文档(本目录已有):
   - `knowledge_bases/bone_density_v1.md`
   - `knowledge_bases/leg_pain_v1.md`
5. 等待 embedding 完成(约 30-60s)
6. 复制 dataset_id

**记录**:
```
DIFY_DATASET_QUESTIONNAIRE = <id>
```

---

## 步骤 4: 创建方案库

1. Dify 控制台 → 知识库 → 创建知识库
2. 名称:`china-charge-solution`
3. 索引模式:高质量
4. 批量上传 `knowledge_bases/solutions/` 下 12 个 markdown:
   ```
   menopause_related.md
   vitamin_d_deficient.md
   calcium_protein_deficient.md
   exercise_deficient.md
   medication_related.md
   fracture_high_risk.md
   muscle_strain.md
   knee_degeneration.md
   lumbar_radiculopathy.md
   gout_inflammatory.md
   vascular_risk.md
   osteoporosis_risk.md
   ```
5. 等待 embedding 完成
6. 复制 dataset_id

**记录**:
```
DIFY_DATASET_SOLUTION = <id>
```

---

## 步骤 5: 替换工作流 yml 中的占位符

```bash
cd /root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow
sed -i "s|<DATASET_PRODUCT>|$DIFY_DATASET_PRODUCT|g" AI_health_consultant_v2.yml
sed -i "s|<DATASET_QUESTIONNAIRE>|$DIFY_DATASET_QUESTIONNAIRE|g" AI_health_consultant_v2.yml
sed -i "s|<DATASET_SOLUTION>|$DIFY_DATASET_SOLUTION|g" AI_health_consultant_v2.yml

# 验证替换完成
grep -n "DATASET_" AI_health_consultant_v2.yml
# 期望:无匹配(已全部替换)
```

---

## 步骤 6: 导入工作流

1. Dify 控制台 → 工作流 → 导入 DSL 文件
2. 选择 `AI_health_consultant_v2.yml`
3. Dify 会自动解析节点;检查:
   - 18 个节点全部识别
   - 3 个 knowledge-retrieval 节点的 dataset_ids 显示为已存在的库
   - 2 个 LLM 节点的模型选择:Doubao-Seed-2.0-lite
4. 点击"发布" → "发布更新"
5. 进入"访问 API"页,复制:
   - `workflow_id`(应是新生成的 ID,与原 `7615498037791588402` 不同)
   - `api_key` (以 `app-` 开头)

**记录**:
```
DIFY_WORKFLOW_HEALTH_CONSULT = AI_health_consultant_v2
DIFY_API_KEY_HEALTH = app-xxxxx
DIFY_WORKFLOW_ID_HEALTH = <新 ID>
```

---

## 步骤 7: 配置后端 `.env.dify-consult`

在 `backend/.env.dify-consult` 中追加(Agent 2 已生成模板):

```dotenv
DIFY_WORKFLOW_HEALTH_CONSULT=AI_health_consultant_v2
DIFY_API_BASE_HEALTH=https://api.dify.ai/v1
DIFY_API_KEY_HEALTH=app-xxxxx
DIFY_DATASET_PRODUCT=<id>
DIFY_DATASET_QUESTIONNAIRE=<id>
DIFY_DATASET_SOLUTION=<id>
APP_CORS_ORIGINS_HEALTH=http://localhost:5173,http://localhost:8082
PORT=8013
```

---

## 步骤 8: 启动后端容器

```bash
cd /root/dify/china_charge_kf
docker compose up -d backend-dify-consult
docker logs -f backend-dify-consult | head -50
```

健康检查:
```bash
curl http://localhost:8013/api/health-consult/health
# 期望: {"status":"ok"}
```

---

## 步骤 9: 冒烟测试(3 个用例)

### 9.1 场景一:骨密度报告
```bash
curl -X POST http://localhost:8013/api/health-consult/chat \
  -F "text=56岁女性已绝经,DXA 腰椎 T值 -2.1 股骨颈 -1.8 全髋 -1.5,骨量减少" \
  -F "session_id=test-001"

# 期望: scene=report, risk_level ∈ {medium,high},
# payload 含 metrics/tValueChart/riskDistribution/oneLineConclusion/questionnaireRef=bone_density_v1
```

### 9.2 场景二:腿疼无危险信号
```bash
curl -X POST http://localhost:8013/api/health-consult/chat \
  -F "text=我腿疼" \
  -F "session_id=test-002"

# 期望: scene=symptom, risk_level=low, payload 含 currentStep/dangerSignals/questionnaireRef=leg_pain_v1
```

### 9.3 场景二:危险信号
```bash
curl -X POST http://localhost:8013/api/health-consult/chat \
  -F "text=一侧小腿突然肿胀发热,按压疼,伴胸闷气短" \
  -F "session_id=test-003"

# 期望: scene=symptom, risk_level=urgent, payload 含 dangerSignals 与 alert(立即就医提示)
```

### 9.4 (可选) 场景二 + 答案归类
```bash
curl -X POST http://localhost:8013/api/health-consult/chat \
  -F "text=" \
  -F "answers={\"trauma\":\"no\",\"swelling\":\"no\",\"chest\":\"no\",\"location\":\"knee\",\"duration\":\"1m\",\"trigger\":\"stairs\"}" \
  -F "session_id=test-004"

# 期望: scene=symptom, risk_level=medium, solutionRef=knee_degeneration_v1
```

---

## 步骤 10: E2E 浏览器验证

1. 浏览器打开 `http://ai.trendpower.cc/chat/?view=health`
2. 屏 1:粘贴骨密度指标 → 发送 → 自动跳屏 2
3. 屏 2:验证 ECharts 柱图 + 环图渲染、风险等级颜色、一句话结论
4. 屏 2 点击"开始分析原因" → 跳屏 3
5. 屏 3:填 12 题量表 → 提交 → 跳屏 4
6. 屏 4:验证 4 张分类卡(lifestyle/nutrition/alert) 内容正确
7. 浏览器控制台:无 404 / 无 CORS / 无 JS error
8. 网络面板:POST /api/health-consult/chat 200 OK,响应 JSON 可解析

---

## 回滚方案

若上线后发现问题,回滚到原 workflow:
1. 把 `DIFY_WORKFLOW_HEALTH_CONSULT` 改回 `AI_health_consultant`(旧 workflow_id `7615498037791588402`)
2. `DIFY_API_KEY_HEALTH` 改回旧 api key
3. `docker compose restart backend-dify-consult`

前端路由 `?view=health` 保持不变,后端降级后仍能工作(只是输出非结构化文本,需前端硬编码 fallback)。
