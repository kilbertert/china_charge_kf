# AI 健康咨询模块 (Health Consult)

> **AI 健康初筛与分诊建议系统**(前端软化命名:"AI 健康风险初筛助手")
>
> 定位:**风险初筛 + 标准化建议**,**不**做疾病诊断 / 药物处方 / 治疗承诺 / 产品推荐 / 替代医生。

---

## 1. 模块定位

为销售小程序新增的合规健康咨询入口,做三件事:

1. **体检报告解读** — 重点支持骨密度 (DXA T值) 报告
2. **身体不适风险甄别** — 重点支持腿疼症状分诊(危险信号筛查 + 标准化方案)
3. **健康产品客观问答** — 复用既有 Dify workflow(场景三,本 MVP 不重构)

**合规约束**(任何文案 / UI / prompt 不得突破):
- 不得出现"AI 医生"/"AI 问诊"/"AI 诊断"等字样
- 危险信号必须明确提示"建议尽快就医"
- 所有 AI 输出必须含"AI 健康初筛建议,不能替代医生诊断"
- 场景三产品问答不得出现"可治疗"/"可替代药物"等违禁词
- 每屏底部必须有"转人工"占位入口

---

## 2. 架构

```
[浏览器] http://ai.trendpower.cc/chat/?view=health
    │
    ↓ HTTP GET
[外层 nginx]
    │
    ├─ /chat/                → 静态文件 /www/wwwroot/ai.trendpower.cc/chat/
    ├─ /chat/api/            → 8012 (Dify 后端,既有)
    └─ /chat/api/health-consult/  → 8013 (health_consult 后端,新增)
                                     ↓
                          health_consult/main:app (FastAPI, uvicorn)
                                     ↓
                          Dify Workflow: AI_health_consultant_v2
                                     ↓
                          3 个知识库 (产品库 / 量表库 / 方案库)
```

**关键设计**:
- **URL 参数隔离** — `?view=health` 走 HealthConsultApp,其他走现有 chat,完全互不污染
- **本地兜底** — Dify 不可达时,`scene_router.py` 用纯关键词匹配继续提供可用响应
- **风险分层确定性** — scene 识别 / 危险信号 / 答案归类全部由 Python `code` 节点 + 本地 scene_router 完成,不依赖 LLM 自由发挥
- **ECharts 按需加载** — 屏 2 才动态 import,屏 1/3/4 不加载

---

## 3. 模块结构

### 3.1 后端: `backend/health_consult/`

```
backend/health_consult/
├── __init__.py
├── main.py              # FastAPI app,路由
├── config.py            # Pydantic Settings (读 .env.dify-consult)
├── dify_proxy.py        # 转发 Dify (复用 app_dify.dify_client.DifyClient)
├── scene_router.py      # 场景识别 + 风险分层 (本地兜底逻辑)
├── questionnaire.py     # 量表定义 (12 题骨密度 + 腿疼 A/B/C)
├── solutions.py         # 方案模板 (6 骨密度 + 6 腿疼)
├── schemas.py           # Pydantic 模型
├── dify_kb_docs/        # 14 份 md (产品/量表/方案三库原始文档)
│   ├── MANIFEST.json
│   └── *.md
├── tests/               # pytest, 97 个用例
│   ├── test_health_endpoint.py
│   ├── test_scene_router.py
│   ├── test_solutions_lookup.py
│   └── test_contract_consistency.py
├── Dockerfile
└── .env.dify-consult    # 实际环境变量 (从 .env.dify-consult.example 复制)
```

### 3.2 前端: `frontend/src/components/HealthConsult/` + `HealthConsultApp.tsx`

```
frontend/src/
├── HealthConsultApp.tsx        # 4 屏主组件 (状态机: chat → report → scale → suggestion)
├── components/HealthConsult/
│   ├── ChatScreen.tsx          # 屏 1: 对话入口
│   ├── ReportScreen.tsx        # 屏 2: 报告可视化 (ECharts)
│   ├── QuestionnaireScreen.tsx # 屏 3: 量表填写
│   ├── SuggestionScreen.tsx    # 屏 4: 方案卡片
│   ├── RiskBadge.tsx           # 风险等级徽章
│   ├── TChart.tsx              # ECharts 柱图
│   ├── DonutChart.tsx          # ECharts 环图
│   └── HealthDisclaimer.tsx    # 合规提示
├── data/
│   ├── questionnaires.ts       # 量表 JSON (fallback)
│   └── solutions.ts            # 方案 JSON (fallback)
├── hooks/
│   └── useSceneChat.ts         # /api/health-consult/chat 封装
└── styles/
    └── health-consult.css
```

### 3.3 Dify 工作流: `Workflow-China_charge_seriver-draft-9380/workflow/AI_health_consultant_v2.yml`

**节点拓扑**:

| 节点 ID | 类型 | 名称 | 说明 |
|---|---|---|---|
| 4001 | start | 开始 | 变量:`input_text`, `input_image`, `input_answers` |
| 4002 | code | scene_classifier | 基于 text+image+answers 输出 scene |
| 4003 | if-else | 路由 | 按 scene 分流 (report / symptom / product) |
| 4010 | llm + code | scene1_骨密度 | LLM 输出 JSON, code 校验提取 |
| 4020 | code + llm | scene2_危险信号 | LLM 识别 input_text 危险信号, code 判断 |
| 4021 | if-else | 是否命中危险信号 | urgent 路径直接出结果 |
| 4022 | knowledge-retrieval | 量表库检索 | 拉取 bone_density / leg_pain 量表 |
| 4023 | variable-aggregator | 屏 3 payload 组装 | 透传量表给前端 |
| 4030 | code + llm | scene2_答案归类 | 按 tag 计算归类标签 |
| 4031 | knowledge-retrieval | 方案库检索 | 按归类标签查方案 |
| 4040 | llm | scene3_产品问答 | 复用现有 yml 的 system prompt |
| 4090 | variable-aggregator | 最终 payload | 统一 {scene, risk_level, payload} |
| 4099 | end | 结束 | 输出变量 `output` = JSON string |

---

## 4. JSON 契约 (跨 Dify / 后端 / 前端)

### 4.1 SceneResponse (主输出)

```typescript
interface SceneResponse {
  scene: "report" | "symptom" | "product";
  risk_level: "low" | "medium" | "high" | "urgent";
  confidence: number;          // 0.0-1.0
  payload: ReportPayload | SymptomPayload | ProductPayload;
}
```

### 4.2 ReportPayload (scene=report, 骨密度)

```typescript
{
  reportType: "bone_density",
  metrics: [{ name: string, value: number, level: string, unit: string }],
  tValueChart: { normal: number, yours: number, thresholds: { normal: number, loss: number } },
  riskDistribution: [{ name: string, value: number }],
  oneLineConclusion: string,
  problemPriority: [{ rank: number, name: string, level: string }],
  questionnaireRef: "bone_density_v1"
}
```

### 4.3 SymptomPayload (scene=symptom, 腿疼)

**初始 (屏 1 → 屏 3 入口)**:
```typescript
{
  symptom: "leg_pain",
  dangerSignals: [],
  currentStep: "danger_signal",
  questionnaireRef: "leg_pain_v1",
  questions: [{ id, text, type, options: [{ key, label, weight }], tag }]
}
```

**完成量表后 (屏 3 → 屏 4)**:
```typescript
{
  riskLevel: "low" | "medium" | "high" | "urgent",
  possibleDirection: string,
  department: string,
  redFlag: string[],
  lifestyle: [{ icon, title, content }],
  nutrition: [{ icon, title, content }],
  solutionRef: "knee_degeneration_v1"
}
```

---

## 5. 本地开发

### 5.1 后端

```bash
cd backend
# 跑测试
python -m pytest health_consult/tests/ -v --tb=short -p "no:solara"
# 期望: 97 passed

# 启动 (Dify API key 留空时走本地兜底)
cp .env.dify-consult.example health_consult/.env.dify-consult
cd ..
python -m uvicorn health_consult.main:app --host 127.0.0.1 --port 8013
```

### 5.2 前端

```bash
cd frontend
npm install                    # 安装 echarts + echarts-for-react
npm run dev                    # Vite dev server
# 访问 http://localhost:5173/?view=health
```

---

## 6. API 端点

所有端点位于 `/api/health-consult` 前缀:

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查,返回 `{status, service, version}` |
| GET | `/version` | 版本 + Dify workflow_id |
| GET | `/questionnaire/{id}` | 拉取量表定义 (bone_density_v1 / leg_pain_v1) |
| GET | `/solution/{scene}/{tag}` | 拉取方案 (scene: report/symptom/product) |
| POST | `/chat` | 主入口,接收 `text` + `files` + `answers` + `session_id`,返回 SceneResponse |

### POST /chat 行为

1. 解析 multipart/form-data
2. 上传文件到 Dify (如有),获取 upload_file_id
3. 组装 workflow inputs,调用 Dify `/v1/workflows/run`
4. 解析 Dify `output` JSON 字段,组装 SceneResponse
5. **失败回退**: Dify 不可达 / API key 缺失 → `scene_router.get_default_scene_response()`

---

## 7. 部署

详见 [DEPLOY.md §6 §7](./DEPLOY.md) — 已包含 health_consult 的 docker-compose 段、nginx location、`scripts/deploy.sh` 使用。

**核心步骤**:

```bash
# 1. 同步代码
scp -r backend/health_consult/ root@124.243.178.156:/root/dify/china_charge_kf/backend/
scp docker-compose.yml root@124.243.178.156:/root/dify/china_charge_kf/

# 2. 构建并启动容器
cd /root/dify/china_charge_kf
docker compose up -d backend-health-consult

# 3. 验证
curl http://ai.trendpower.cc/chat/api/health-consult/health
# {"status":"ok","service":"health-consult","version":"0.1.0"}
```

---

## 8. Dify 工作流部署

详见 `Workflow-China_charge_seriver-draft-9380/DEPLOY_INSTRUCTIONS.md` (Agent 1 编写)。

**核心步骤**(需在 Dify Web 控制台手动完成):
1. 创建 3 个知识库:产品库 / 量表库 / 方案库
2. 上传 `backend/health_consult/dify_kb_docs/` 下的 14 份 md 到对应 dataset
3. 在 Dify Studio 导入 `AI_health_consultant_v2.yml`
4. 把 3 个 dataset_id 填入 yml 的 `<DATASET_PRODUCT>` / `<DATASET_QUESTIONNAIRE>` / `<DATASET_SOLUTION>` 占位符
5. 发布,获取 workflow_id + API key
6. 把 API key 写入 `backend/.env.dify-consult` 的 `DIFY_API_KEY`

---

## 9. 风险与已知问题

| 风险 | 缓解 |
|---|---|
| Dify LLM 输出 JSON 不稳定 | system prompt 强制 JSON,code 节点正则兜底,失败时降级到本地 scene_router |
| ECharts 在低端机卡顿 | 动态 import,屏 2 才加载 |
| 三场景优先级误判 | scene_router 加 confidence 字段,<0.6 时回到对话屏让用户重选 |
| 新模块污染现有 chat | URL 参数 `?view=health` 完全隔离,失败回退到 chat |
| 危险信号漏判 | 双重判定 — Dify 端 LLM + 本地 scene_router 关键词匹配,任一命中即 urgent |
| 场景三产品问答超规 | 沿用现有 yml 的 system prompt 限制,本期不重构 |

**已知遗留 TODO**:
- 场景三 (产品问答) 深度重构待后续
- 多语言(只做中文,en/vi 后续)
- 转人工实际对接 — 只放占位按钮
- 营养师/医生审核后台
- A/B 测试、监控、灰度

---

## 10. 测试覆盖

97 个 pytest 用例,覆盖:
- `test_scene_router.py` — 三场景分流 + 危险信号识别 (28 用例)
- `test_health_endpoint.py` — FastAPI 端点 (11 用例)
- `test_solutions_lookup.py` — 方案查找 (19 用例)
- `test_contract_consistency.py` — JSON 契约一致性 (12 用例)

`confusion matrix`:
- report (骨密度) — 7 个 keyword 组合
- symptom (腿疼) — 10 个场景 + 5 个危险信号变体
- product (营养问答) — 5 个产品关键词
- 紧急路径 (urgent) — 4 个危险信号场景

---

## 11. 验收清单

- [x] 4 屏状态机联动 (chat → report → scale → suggestion)
- [x] ECharts 柱图 + 环图渲染
- [x] 风险等级颜色编码 (low 绿 / medium 橙 / high 红 / urgent 深红)
- [x] 危险信号 urgent 直出,不再走量表
- [x] 量表 + 答案归类 → 方案卡
- [x] 7 套固定方案 (6 腿疼 + 6 骨密度,部分共用)
- [x] 兜底逻辑: Dify 不可达时本地 scene_router
- [x] 合规提示: 每屏顶部 / 底部 disclaimer
- [x] 转人工占位按钮
- [x] 14 份知识库 md 文档
- [x] 97 个 pytest 用例全通过
- [x] 部署到生产服务器 124.243.178.156
- [x] nginx location /chat/api/health-consult/ 已配置
- [x] 容器健康检查通过
