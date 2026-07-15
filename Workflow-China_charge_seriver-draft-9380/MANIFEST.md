# AI 健康咨询模块 — Dify 工作流 manifest

> 由 Agent 1(Dify 架构师)产出。模块工作流与知识库索引。

## 模块概览

- **模块名**:AI 健康咨询(AI Health Consult)
- **MVP 范围**:场景一(骨密度报告解读)+ 场景二(腿疼症状甄别),场景三(产品问答)走知识库
- **核心契约**:SceneResponse JSON `{scene, risk_level, confidence, payload}` (统一由 End 节点 `output` 字段输出)
- **合规边界**:AI 不做诊断、不开药、不承诺疗效;危险信号强制就医;产品问答以知识库为主

## 工作流 DSL

| 项 | 值 |
|----|---|
| 名称 | `AI_health_consultant_v2` |
| DSL 文件 | `workflow/AI_health_consultant_v2.yml` |
| 节点 ID 范围 | 4001-4099(原 3001-3015 保留不动) |
| 节点数 | 18(15 + 3 答案归类支路) |
| 边数 | 20 |
| Start 变量 | `input_text` / `input_image` / `input_answers`(JSON 字符串) / `input_session_id` / `input_language` |
| End 输出 | `output` = SceneResponse JSON 字符串 |

### 节点拓扑

| ID | 类型 | 名称 | 职责 |
|----|------|------|------|
| 4001 | start | 开始 | 接收 5 个入参变量 |
| 4002 | code | scene_classifier | 基于文本/图片/答案关键词分流(确定性,无 LLM 自由发挥) |
| 4003 | if-else | 路由-按scene | 3 路:report / symptom / product |
| 4010 | llm (vision) | scene1_LLM_骨密度提取 | 从文本+图片提取骨密度指标 JSON |
| 4011 | code | scene1_code_JSON+T值分级 | 解析 LLM JSON,做确定性 T 值分级(T≥-1 正常 / -2.5<T<-1 骨量减少 / T≤-2.5 骨质疏松) |
| 4020 | llm | scene2_LLM_危险信号识别 | 识别 9 类危险信号关键词 |
| 4021 | code | scene2_code_危险信号判定 | LLM 失败时关键词兜底,输出 `urgent` 布尔 |
| 4022 | if-else | 路由-是否urgent | urgent=true → 紧急路径;false → 量表路径 |
| 4023 | code | scene2_urgent_payload | 紧急路径:返回 urgent SceneResponse(血管/神经/感染排查) |
| 4024 | knowledge-retrieval | 量表库检索 | 拉取 leg_pain_v1 量表 JSON |
| 4025 | variable-aggregator | scene2_屏3_payload | 组装屏 3 量表 payload(currentStep=danger_signal, questions) |
| 4026 | code | scene2_code_答案归类 | 按 leg_pain 答案 location/trigger/history 计算归类 tag |
| 4027 | knowledge-retrieval | 方案库检索 | 按归类 tag 检索对应方案 |
| 4028 | variable-aggregator | scene2_屏4_payload | 组装屏 4 方案 payload |
| 4030 | knowledge-retrieval | 产品库检索 | 从产品库检索与客户问题相关的产品 |
| 4031 | llm | scene3_LLM_产品问答 | 基于产品库回答(不能替代药物/诊断) |
| 4090 | variable-aggregator | 最终payload聚合 | 4 路 scene 合并到 `output` |
| 4099 | end | 结束 | 输出 `output` = SceneResponse JSON 字符串 |

## 知识库

| 库 | dataset_id 占位 | 文档数 | 用途 |
|----|-----------------|--------|------|
| 产品库 | `<DATASET_PRODUCT>` | 0(待补) / 复用现有 `cJ687...` | 场景三 RAG 检索 |
| 量表库 | `<DATASET_QUESTIONNAIRE>` | 2(bone_density_v1 + leg_pain_v1) | 场景二屏 3 拉量表 |
| 方案库 | `<DATASET_SOLUTION>` | 12(6+6 种) | 答案归类后查方案 |

详见 `knowledge_bases/README.md`。

## 与 plan 的偏离

1. **新增节点 4026/4027/4028**:plan 表只列了 `4030 code + llm scene2_答案归类` 单节点(对应"scene2_答案归类"),本设计拆为 3 个节点(code 归类 + KR 检索 + VA 聚合),原因是 Dify 的 code 节点无法同时做"RAG 触发"操作,必须拆出 KR 节点。
2. **scene1 增加 vision 能力**:plan 中 4010 是纯 LLM 节点,实际给 4010 加了 `vision.enabled=true` 以支持图片报告 OCR(原 workflow 已支持)。
3. **scene_classifier 用 code 节点而非 question-classifier**:Dify 0.6.0 的 question-classifier 不支持多变量输入,且 answers 是 JSON 字符串难以拆 key,用 code 节点确定性 if-elif 更稳健。
4. **scene3 产品问答走 code-free LLM**:plan 提到 scene3 复用现有 yml 兜底,本设计在 v2 中独立实现(scene3 LLM 节点),不依赖原 yml,更可控。

## 关键设计要点

- **不依赖 LLM 自由生成结构**:scene 识别、tag 计算、JSON 校验、T 值分级、危险信号判定全部用 code 节点做确定性逻辑
- **LLM 失败兜底**:scene1 LLM 输出失败时,code 节点用正则提取 JSON;scene2 LLM 失败时,code 节点用关键词兜底
- **三处 knowledge-retrieval 节点**:均用占位符 `<DATASET_*>`,部署时由 Agent 4 替换为真实 dataset_id
- **End 节点统一输出**:`output` 变量即 SceneResponse JSON 字符串,后端 `response_parser` 只需做 JSON 解析(无需 XSS/正则兜底)
- **node ID 范围 4001-4099**:避开原 3001-3015,降低未来合并冲突风险

## 部署指引

见 `DEPLOY_INSTRUCTIONS.md`(由 Agent 4 执行)。
