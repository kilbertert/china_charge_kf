# yml 节点拓扑设计 - SPEC-A3

> 状态: Phase 1 收尾设计,后续 B1/C/D/E 全部按此施工
> 关联: docs/03_REFACTOR_SPEC.md SPEC-A3,docs/04_CONTRACT_SCENE_RESPONSE.md
> 借鉴: AI_health_consultant_v2.yml (node ID 4001-4099),本工作流用 5001-5099 避让

---

## 1. 节点 ID 分配表

| 节点 ID | 名称 | 类型 | SPEC | 关闭缺口 |
|---------|------|------|------|----------|
| 5001 | start | start | - | - |
| 5002-1 | code_4维关键词匹配 | code | B1 | G1 |
| 5002-2 | KR_FAQ | knowledge-retrieval | B1 | G1 |
| 5002-3 | code_FAQ包装 | code | B1 | G1 |
| 5002-4 | llm_4维意图分类 | llm | B1 | G1 |
| 5002-5 | code_fallback_scene | code | B1 | G1 |
| 5003 | if-else_scene | if-else | B1 | G1 |
| 5011 | 流程1_KR_功能匹配 | knowledge-retrieval multi_retrieval | C1 | G3 |
| 5012 | code_流程1验证 | code | C1 | G3 |
| 5013 | 流程2_KR_清单校验 | knowledge-retrieval multi_retrieval | C2 | G4 |
| 5014 | code_流程2验证 | code | C2 | G4 |
| 5015 | 流程3_KR_报价 | knowledge-retrieval | C3 | G5 |
| 5010 | llm_功能咨询 | llm | D1 | G6 |
| 5017 | code_步骤包装 | code | D1 | G6 |
| 5020 | code_危险信号判定 | code HTTP 拉后端 | D2 | G7 G10 |
| 5021 | llm_业务诊断 | llm | D2 | G7 |
| 5022 | code_紧急路径 | code | D2 | G7 G15 |
| 5030 | 步骤检索_KR | knowledge-retrieval multi_retrieval | D3 | G8 G12 |
| 5031 | llm_多语言指引 | llm | D3 | G8 G11 |
| 5032 | code_保留跳转链接 | code | D3 | G8 |
| 5040 | code_FAQ直查返回 | code | B1 | G1 |
| 5050 | code_报价结构化 | code | C3 | G5 |
| 5090 | code_fallback_scene | code | B1 | G1 |
| 5080 | variable-aggregator | variable-aggregator | E1 | G9 |
| 5081 | code_打包SceneResponse | code | E1 | G9 |
| 5099 | end | end | E1 | G9 |

节点总数: 26 个

---

## 2. 整体拓扑

```
5001 start
  |
5002-1 code_4维关键词匹配 (21 FAQ 节点 + 4 维关键词)
  |--FAQ 命中--> 5002-2 KR_FAQ --> 5002-3 code_FAQ包装 --|
  |--场景命中-------------------------------------|     |
  |--都不命中--> 5002-4 llm_4维意图分类 --> 5002-5 code_fallback_scene
                                                       |
                                            5003 if-else_scene
                                            |--scene=pricing--> 5050 报价
                                            |--scene=after_sales--> 5020-5022 危险诊断
                                            |--scene=faq--> 5040 FAQ 返回
                                            |--scene=fallback--> 5090 fallback
                                                       |
                  后台三流(并行): 5011 5012 / 5013 5014 / 5015
                                                       |
                                            5080 variable-aggregator
                                                       |
                                            5081 code_打包SceneResponse
                                                       |
                                            5099 end (ChargeSceneResponse JSON)
```

---

## 3. 各路径内部拓扑

### 3.1 路径 A - 功能查询 (5010-5017)
5003 -> 5010 llm_功能咨询 (input: input_text + 5011/5013 result) -> 5017 code_步骤包装 -> 5080

### 3.2 路径 B - 业务/规则诊断 (5020-5022)
5003 -> 5020 code_危险信号判定 (HTTP GET 后端)
- 命中危险 -> 5022 code_紧急路径 (直接输出,跳过 5021)
- 不命中 -> 5021 llm_业务诊断 (multi_retrieval fault+faq weights 0.8+0.2) -> 5080

### 3.3 路径 C - 操作指导 (5030-5032)
5003 -> 5030 步骤检索_KR (multi_retrieval operation_guide, metadata filter endpoint+language) -> 5031 llm_多语言指引 -> 5032 code_保留跳转链接 (提取 deep_link) -> 5080

### 3.4 路径 D - FAQ 直查 (5040)
5002-3 -> 5080 (跳过 5003 路由)

### 3.5 路径 E - 报价 (5050)
5003 -> 5050 code_报价结构化 (解析 5015 result) -> 5080

### 3.6 路径 F - fallback (5090)
5003 -> 5090 code_fallback_scene -> 5080

---

## 4. 关键数据流示例

### 4.1 售前 (7kW 充电桩多少钱?)
5001 -> 5002-1 (scene=pricing, endpoint=user, region=cn, pile_type=public, conf=0.95)
-> 后台三流 5011/5013/5015 并行
-> 5003 -> 5050 -> 5080 -> 5081 -> 5099
output.payload: {text, flow1_matched=true, flow2_verified=true, flow3_pricing, pricing_table: [...]}

### 4.2 危险信号优先 (我的桩漏电了)
5001 -> 5002-1 (危险漏电命中 -> scene=after_sales, endpoint=user)
-> 5003 -> 5020 (HTTP GET /api/charge-consult/danger-keywords?endpoint=user)
-> 命中漏电 -> 5022 code_紧急路径 (跳过 5021 LLM)
-> 5081 打包
output.payload.danger.matched=true, risk_level=urgent, next_actions: [call_support, create_ticket (placeholder)]

### 4.3 FAQ 直查 (Role Management 权限怎么分配?)
5001 -> 5002-1 (命中 FAQ node Role Management, endpoint 推断为 pc)
-> 5002-2 KR_FAQ -> 5002-3 code_FAQ包装 -> 5080 (跳过 5003)
output.payload.faq.matched=true, node=Role Management, answer_hash=...

---

## 5. 节点 ID 命名约定

- 5001-5099 区间:本工作流专属
- 末位 1: start / 流程1 / 路径 A 第一节点
- 末位 0: llm / 路径主入口
- 末位 2: code 验证节点 / LLM 辅助节点
- 末位 3-7: 各路径内的 LLM + code 节点
- 末位 9: end 节点 (5099)

---

## 6. 边与循环

- 无环: Dify workflow 不允许有向环
- 多路并行: 后台三流 5011/5013/5015 并行
- 多路汇聚: 4 个路径都汇到 5080 aggregator
- 无孤儿: 每个非 start 节点至少一条入边

---

## 7. 占位符约定 (借鉴 DEPLOY_INSTRUCTIONS.md 步骤 5)

| 占位符 | 含义 | 节点 |
|--------|------|------|
| DATASET_PRODUCT_SPEC | 产品功能矩阵 | 5011, 5010 |
| DATASET_PRODUCT_CHANGELOG | 版本变更日志 | 5013 |
| DATASET_PRICING | 报价表 | 5015 |
| DATASET_FAULT_DIAGNOSIS | 故障诊断手册 | 5021 |
| DATASET_OPERATION_GUIDE | 操作手册 (多语言) | 5030 |
| DATASET_FAQ | 常见问题 (21 节点) | 5002-2 |
| API_DANGER_KEYWORDS | 危险信号 API URL | 5020 |

yml 中用尖括号包起来 <DATASET_*>,部署时 sed 替换为真实 dataset_id

---

## 8. 实施分阶段

| 阶段 | 节点范围 | SPEC | 验证方式 |
|------|----------|------|----------|
| Stage 1 骨架 | 5001, 5002-1/4/5, 5003, 5080, 5081, 5099 | B1 + E1 基础 | Dify 控制台导入能跑通 |
| Stage 2 后台三流 | 5011-5015 | C1, C2, C3 | 关键词命中测试 |
| Stage 3 路径 A/C | 5010, 5017, 5030-5032 | D1, D3 | 5 条 curl 用例 |
| Stage 4 路径 B | 5020-5022 | D2 | 6 危险 + 4 非危险 |
| Stage 5 路径 D FAQ | 5002-2, 5002-3, 5040 | B1 FAQ | 21 节点逐个命中 |
| Stage 6 路径 E 报价 | 5050 | C3 | 3 SKU x 3 region |
| Stage 7 路径 F fallback | 5090 | B1 fallback | 空文本 + 模糊 |

---

## 9. 风险与开放问题

1. 5010 LLM 上下文大小: 5011+5013 的 KR result 可能很长, top_k=3 限制
2. 5020 HTTP 超时: 后端不可用会拖慢, 200ms 超时 + 失败降级本地 hardcode
3. multi_retrieval 在 Dify 实际支持: 需 prod Dify >= 0.7
4. session_id 跨实例路由: SPEC-A2 设计,放后端 Redis

---

## 10. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-06-18 | 初版, SPEC-A3 完整节点拓扑 + 4 维 + 3 个数据流示例 |