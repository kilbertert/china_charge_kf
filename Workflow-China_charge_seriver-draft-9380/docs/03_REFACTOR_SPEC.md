# 重构 SPEC 拆解 — 充电桩客服工作流 v2

> 来源: `docs/01_ARCHITECTURE_UNDERSTANDING.md` + `docs/02_CAPABILITY_GAP.md`
> 用途: 后续施工的 checklist,每条 SPEC 独立可勾选、独立可验证。
> 关联 yml: `workflow/China_charge_seriver.yml`(新建 v2,文件名待定)
> 借鉴模板: `workflow/AI_health_consultant_v2.yml`(node ID 范围 4001-4099,本工作流用 **5001-5099**)

---

## 1. SPEC 总览表

| SPEC | 标题 | 优先级 | 关闭的缺口 | 前置依赖 | 估计节点数 |
|------|------|--------|------------|----------|------------|
| SPEC-A1 | SceneResponse 输出契约设计 | P0 | G9 | 无 | 0(纯设计) |
| SPEC-A2 | 多轮 session/turn 状态设计 | P0 | G2, G14 | A1 | 0(纯设计) |
| SPEC-A3 | yml 节点拓扑整体设计 | P0 | G1-G15 总览 | A1, A2 | 0(纯设计) |
| SPEC-B1 | scene_classifier 实现 | P0 | G1 | A3 | 1~2 |
| SPEC-C1 | 流程1 — 功能匹配预检 | P1 | G3, G12 | A3, F1 | 2(KR + code) |
| SPEC-C2 | 流程2 — 清单校验 | P1 | G4 | A3, F2 | 2(KR + code) |
| SPEC-C3 | 流程3 — 报价查询 | P1 | G5 | A3, F3 | 1(KR) |
| SPEC-D1 | 路径 A — 功能查询/检查 | P1 | G6 | A3, C1 | 2(KR + LLM) |
| SPEC-D2 | 路径 B — 业务/规则诊断(含危险信号硬闸门) | P0 | G7, G10, G15 | A3, F4 | 3(code + LLM + 兜底) |
| SPEC-D3 | 路径 C — 移动设备操作指导 | P1 | G8, G11 | A3, F5 | 2(KR + LLM) |
| SPEC-E1 | End 节点聚合 + SceneResponse JSON 打包 | P0 | G9 | 所有 D | 2(aggregator + code) |
| SPEC-F1 | 知识库数据补全(5 个数据集) | P1 | G12, G13 | 无 | 0(纯数据) |
| SPEC-G1 | 后端协同(ChargeSceneResponse + scene_router) | P0 | (后端) | A1 | 0(纯代码) |
| SPEC-H1 | 部署与端到端冒烟测试 | P0 | 全部 | 所有 | 0(部署 + 测试) |

---

## 2. SPEC 详细说明

### SPEC-A1 — SceneResponse 输出契约设计 [P0]

**关闭缺口**: G9

**目标**: 定义 End 节点输出的统一 JSON 结构,供前端按 scene 渲染不同 UI。

**交付物**:
- `docs/04_CONTRACT_SCENE_RESPONSE.md`(本工作流新增,可选)
- 或直接在 SPEC 文档中给出 schema 示例

**最小 schema(借鉴健康咨询 v2)**:
```json
{
  "scene": "pre_sale | after_sales | operation | pricing | fallback",
  "risk_level": "low | medium | high | urgent",
  "confidence": 0.0,
  "payload": {
    "text": "...",
    "structured": {
      "flow1_matched": true | false,
      "flow2_verified": true | false,
      "flow3_pricing": "..." | null,
      "scene_specific": {...}
    },
    "next_actions": [...]
  }
}
```

**验收**:
- [ ] schema 字段固定,前端可写 TypeScript type 强校验
- [ ] 与健康咨询的 SceneResponse 兼容(共用后端解析逻辑)
- [ ] 包含 `fallback` scene,用于兜底

---

### SPEC-A2 — 多轮 session / turn 状态设计 [P0]

**关闭缺口**: G2, G14

**目标**: 支持两轮对话 + 第三轮之后回流。

**决策点**:
- session 状态放 Dify `conversation_variables` 还是后端 Redis?
- 借鉴:`AI_health_consultant_v2.yml` 没用到 conversation_variables,所以本工作流可能也不需要 Dify 这层,放后端更可控

**最小实现**:
- start 新增变量:`input_session_id`、`input_turn`(默认 1)
- 第二轮输入时由后端把上一轮的三流结果作为额外变量传入(可选 `input_context_json`)
- End 输出再把状态写回给后端,由后端 Redis 持久化

**验收**:
- [ ] start 节点支持 session_id 和 turn 输入
- [ ] 后端能基于 session_id 召回上一轮的三流结果
- [ ] 跨轮次 `scene` 字段可回放(同一 session 的所有 turn 一致,除非用户切换意图)

---

### SPEC-A3 — yml 节点拓扑整体设计 [P0]

**关闭缺口**: 所有缺口的总览依赖

**目标**: 在写代码前,先在文档里画清楚节点 ID 分配、边走向、数据流。

**交付物**:
- `docs/05_NODE_TOPOLOGY.md`(本工作流新增)

**最小拓扑**:
```
[5001 start]
   ↓
[5002 scene_classifier] — code 节点,关键词 + JSON 输入分流
   ↓ (输出 scene 字段)
[5003 if-else] — 按 scene 分 4 路
   ├─ pre_sale      → [5010 路径A]
   ├─ after_sales   → [5020 路径B]
   ├─ operation     → [5030 路径C]
   └─ pricing/fallback → [5090 fallback]

[并行三流,所有路径共享]
[5011 流程1_KR] → [5012 流程1_code_验证]
[5013 流程2_KR] → [5014 流程2_code_验证]
[5015 流程3_KR]

[路径A: 5010 LLM_功能] → [5017 步骤包装]
[路径B: 5020 危险信号_code] → [5021 LLM_诊断] / [5022 紧急路径]
[路径C: 5030 步骤检索_KR] → [5031 多语言LLM_指引]

[5080 variable-aggregator] — 4 路合并
[5081 code_打包SceneResponse]
[5099 end] — output = SceneResponse JSON
```

**验收**:
- [ ] 节点 ID 在 5001-5099 范围内(避让其他工作流)
- [ ] 每个 SPEC 的节点都体现在此拓扑
- [ ] 边无环、无孤儿

---

### SPEC-B1 — scene_classifier 实现(含 FAQ 直查 + 4 维分类) [P0]

**关闭缺口**: G1

**目标**: 在 5002 节点识别用户意图,输出 **4 维 scene 字段**。FAQ 类问题直接走知识库固定答案,跳过 LLM 自由生成。

**实现方式决策(已对齐)**:
- **方案 Z — code + LLM 混合** ✅ 锁定
- **新增子流程 B1-FAQ 直查**: 用户问题命中 FAQ 关键词标签时,直接走知识库固定答案,完全跳过 LLM,保证 FAQ 类答案一致性

**4 维分类体系(基于实际资料推导)**:

| 维度 | 取值 | 数据源 |
|------|------|--------|
| 业务意图(scene) | pre_sale / after_sales / operation / pricing / faq / fallback | 关键词 + LLM |
| 端类型(endpoint) | user / butler / pc | 关键词 + LLM(用户端/管家端/PC 后台) |
| 地域(region) | cn / overseas | `language` 变量 + 关键词(海外独有"谷歌/脸书") |
| 桩型(pile_type) | public / home(V2.4 新增) | 关键词(家充/家用/私人桩) |

**节点拓扑(扩为 5 个)**:
```
[5002-1 code_4维关键词匹配]
    ├─ 命中 FAQ 节点(21 个) → [5002-2 KR_FAQ] → [5002-3 code_FAQ包装] → 直接输出
    ├─ 命中场景关键词 → 返回 scene 字段(高置信度)
    └─ 都不命中 → [5002-4 llm_4维意图分类] → 返回 scene 字段(降级)
       └─ LLM 失败 → [5002-5 code_fallback_scene] → fallback
```

**输出**:
```python
return {
    "scene": "pre_sale | after_sales | operation | pricing | faq | fallback",
    "endpoint": "user | butler | pc",
    "region": "cn | overseas",
    "pile_type": "public | home",
    "confidence": 0.0~1.0,
    "reason": "...",
    "is_faq": bool,
    "faq_answer": str | None,  # 仅当 is_faq=true 时非空
    "matched_faq_node": str | None,  # 21 个节点之一
}
```

**FAQ 关键词标签(21 个,基于 `常见问题解答.xlsx` 实际数据)**:
```
Role Management / Shop Level / Individual operator / Operator review for entry
/ Add sites under the operator / Site audit / Billing Template / Charging Order
/ Charging coupons / Create venue / Data View / Data sector / Equipment Failure List
/ Financial Management / Operations Management / Order Management / Placement equipment
/ Real name authentication / Sign up / Venue / Venue association template
/ equipment / place an order / top-up
```
(注: 21 个但上面列了 24 个,因为有的节点如 Sign up 跨用户端/管家端)

**验收**:
- [ ] FAQ 关键词标签命中时,100% 走 KB 直查,**不调用 LLM**
- [ ] 场景关键词命中时,高置信度(scene 100% 锁定)
- [ ] 4 维分类(scene + endpoint + region + pile_type)任一不明确时,降级到 LLM
- [ ] LLM 失败再降级到 `fallback` scene
- [ ] FAQ 答案与知识库原文一致(代码层面做 hash 校验)
- [ ] "家充"关键词(家充/家用/私人桩)命中时 pile_type=home
- [ ] "谷歌登录/脸书登录"命中时 region=overseas

---

### SPEC-C1 — 流程1 — 功能匹配预检(multi_retrieval + 4 维过滤) [P1]

**关闭缺口**: G3, G12

**目标**: 第一轮进入时,在产品功能矩阵 KB 中检索,确认用户提到的功能是否覆盖。**采用 multi_retrieval 多库一起查**。

**节点**:
- 5011 `knowledge-retrieval`(**multi_retrieval 模式**,top_k=3,score_threshold=0.7)
  - 检索范围:[`<DATASET_PRODUCT_SPEC>`, `<DATASET_PRODUCT_CHANGELOG>`]
  - 一并扫两个库,功能矩阵 + 版本变更日志一起回
  - metadata filter:`endpoint ∈ {scene.endpoint, *} AND region ∈ {scene.region, *} AND pile_type ∈ {scene.pile_type, *}`
- 5012 `code_流程1验证`(检查 result 是否非空,生成 `flow1_matched: bool`)

**数据集字段(基于 `趋势云-标准充电桩功能清单V2.4.1.xlsx` 实际结构)**:
```
板块 | 模块 | 功能点 | 功能说明 | 备注 | 端类型(用户/管家/PC) | 版本(V2.x) | 是否家充 | 地域(国内/海外)
```

**multi_retrieval 配置要点**:
- 权重(weights):功能矩阵 0.7,变更日志 0.3(变更日志只用于版本校验,不主导匹配)
- reranking_enable: true
- 两库合并后做重排,取综合 Top-K

**端/地域/桩型过滤的重要性(由实际资料推导)**:
- 海外版独有"谷歌/脸书第三方登录"(V2.1+),用户问"怎么用谷歌登录"时若不按 region 过滤,会拉出国内版的"微信小程序登录",答案错配
- 家充场景(V2.4+)独有"私人桩绑定",公共桩用户问"绑定桩"应拉公共桩文档
- 三端(用户/管家/PC)功能矩阵差异大,过滤不到位会跨端串答案

**验收**:
- [ ] 输入"定时充电" + endpoint=user → flow1_matched=true(用户端有此功能)
- [ ] 输入"声纹解锁" → flow1_matched=false(未实现功能)
- [ ] 输入"谷歌登录" + region=overseas → 命中海外用户端登录功能
- [ ] 输入"微信登录" + region=overseas → 命中为空(海外版无此功能)
- [ ] 输入"绑定私人桩" + pile_type=home → 命中家充功能
- [ ] 输入为空 + 无图片 → 返回 flow1_matched=null
- [ ] 功能矩阵和变更日志两个库都参与检索,结果合并重排

---

### SPEC-C2 — 流程2 — 清单校验(由 C1 multi_retrieval 覆盖,独立 code 节点保留) [P1]

**关闭缺口**: G4

**目标**: 校验流程1命中的功能描述是否与最新版本/固件一致。

**节点**:
- 5013 `knowledge-retrieval`(由 **SPEC-C1 的 multi_retrieval 合并检索** 直接覆盖,不再独立建 KR)
- 5014 `code_流程2验证`(独立 code 节点,基于 multi_retrieval 结果里的 `<DATASET_PRODUCT_CHANGELOG>` 部分做版本比对)

**数据集占位**: 复用 `<DATASET_PRODUCT_CHANGELOG>`(由 SPEC-F1 创建)

**痛点对应**: 此处是架构图黄色注释"新增策略而检查麻烦"的核心位置,实现时必须保证:
- 新增功能时,只需在 changelog 库追加文档,**不需要改 yml**
- 校验逻辑完全由 code 节点根据文档结构做,不写死版本号
- 因为 multi_retrieval 已合并,流程2 KR 节点本身被吃掉,只剩 code 验证节点

**验收**:
- [ ] 流程1 multi_retrieval 后,流程2 code 节点必跑
- [ ] 流程1未命中时,流程2 result 显式为 null,不报错
- [ ] changelog 新增条目后,yaml 无需修改

---

### SPEC-C3 — 流程3 — 报价查询 [P1]

**关闭缺口**: G5

**目标**: 第一轮进入时,在报价库中检索产品价格/配件价/保修期价格。

**节点**:
- 5015 `knowledge-retrieval`(单库,top_k=2,score_threshold=0.75,query_variable_selector=input_text)

**数据集占位**: `<DATASET_PRICING>`(由 SPEC-F3 创建)

**与功能流的隔离**:
- 报价独立 KB,不与功能库混
- 报价 LLM prompt 严格禁止添加"促销推荐"等模糊话术
- 价格必须从 KB 原文复制,不允许 LLM 编造

**验收**:
- [ ] 输入"7kW 充电桩多少钱" → 返回准确价格
- [ ] 输入"充电枪头" → 返回配件价
- [ ] KB 命中为空 → 返回"暂无报价,请联系销售"

---

### SPEC-D1 — 路径 A — 功能查询 / 检查 [P1]

**关闭缺口**: G6

**目标**: 路径 A 输出"知识性问答 + 功能清单"。

**节点**:
- 5010 `llm`(基于流程1+流程2结果 + 兜底 KB)
- 5017 `code_步骤包装`(可选,把 LLM 输出拆成 text + structured list)

**数据集依赖**: 流程1/2 的 result + 兜底 `cJ687...`

**验收**:
- [ ] 纯知识问答("保修期多久") → 返回直接答案
- [ ] 功能清单问答("这桩有什么功能") → 返回结构化清单
- [ ] 输入有图片(铭牌) → LLM 利用 vision 解析后回答

---

### SPEC-D2 — 路径 B — 业务 / 规则诊断(含危险信号硬闸门 + 端感知) [P0]

**关闭缺口**: G7, G10, G15

**目标**: 路径 B 必须先做危险信号判定,再进入诊断。**按端类型区分关键词清单**。

**节点(四段式)**:
- 5020 `code_危险信号判定` — 关键词硬判定,**按 endpoint 分组加载关键词**
  - **用户端关键词**: 漏电、过热、异味、火花、烧焦、断电、冒烟、击穿、跳闸后无法复位……(C 端用户报障常用语)
  - **管家端关键词**: 设备离线、设备故障、SN 码错误、投放失败、计费异常……(B 端运营常用语)
  - **PC 后台关键词**: 系统告警、对账不平、分润异常、退款堆积……
  - 输出:`urgent: bool`、`danger_signals: list`、`endpoint_match: str`
  - **关键词列表维护位置(已对齐):由后端负责维护,通过 HTTP 节点调后端接口 `GET /api/charge-consult/danger-keywords?endpoint=user|butler|pc` 获取最新关键词**(不进 Dify yml)
- 5021 `llm_业务诊断` — 仅在 urgent=false 时执行,做规则/流程诊断
- 5022 `code_紧急路径` — urgent=true 时执行,直接返回"立即停用 + 联系售后" SceneResponse
- 5023 `code_端感知分流`(新增) — endpoint=butler 时,优先输出"管家端工单流程";endpoint=user 时,优先输出"用户自助排查步骤"

**数据集占位**: `<DATASET_FAULT_DIAGNOSIS>`(来源:操作手册 `Equipment Failure List` + `Fault Repair` 章节)

**数据集字段(基于操作手册实际章节)**:
```
故障码 | 现象 | 可能原因 | 排查步骤 | 兜底建议 | 端类型(用户/管家/PC) | 是否家充
```

**与 FAQ `<DATASET_FAQ>` 的 multi_retrieval**:
- KR 同时检索 `<DATASET_FAULT_DIAGNOSIS>` 和 `<DATASET_FAQ>`,FAQ 节点 `equipment`(5 条)和 `Equipment Failure List`(1 条)作为补充
- weights: 故障诊断 0.8, FAQ 0.2(故障类问题主导)

**兜底(G15 — 已对齐)**: 当前无工单 API,后续拓展
- 5022 输出 `next_actions = ["call_human_support"]`(纯文字建议,不实际创建工单)
- 后端 `scene_router_charge` 需要预留 `create_ticket(scene_payload)` 函数,**函数体暂为 NotImplementedError**,工单 API 就绪后填实现
- 关键词维护和工单 API 都放在后端,避免 Dify yml 因运维变更频繁改动

**验收**:
- [ ] 用户端关键词命中 → 5022 输出"立即停用 + 联系售后(用户热线)"
- [ ] 管家端关键词命中 → 5022 输出"立即停用 + 提交管家端工单"
- [ ] 关键词未命中 + 描述模糊 → 5021 LLM 判定后给出诊断
- [ ] 5021 LLM 失败 → 兜底提示"请补充故障码 + 指示灯状态"
- [ ] 后端危险信号关键词列表可通过 HTTP 接口按 endpoint 热更新,**不需改 yml 重新部署**
- [ ] 工单创建函数保留入口,无工单 API 时不报错,仅返回文字建议

---

### SPEC-D3 — 路径 C — 移动设备操作指导(三端 × 多语言 zh/en/vi) [P1]

**关闭缺口**: G8, G11

**目标**: 路径 C 输出"步骤化、可执行"的操作指引,按**端类型 + 用户语言**输出。保留原文中的跳转链接。

**节点**:
- 5030 `knowledge-retrieval`(**multi_retrieval 模式**,覆盖 `<DATASET_OPERATION_GUIDE>` 三语言文档)
  - metadata filter:`endpoint=scene.endpoint AND language=input_language`
- 5031 `llm_多语言指引`(强制按 input_language 输出,prompt 里硬约束)
- 5032 `code_保留跳转链接`(新增)— 把 KB 段落中含 `/charge/pages/...` 的链接字符串提取出来,附加到输出步骤末尾

**数据集占位**: `<DATASET_OPERATION_GUIDE>`(来源:`Standard Operating Manual for Charging Piles.docx` 190 段 + 中译英版 194 段)

**数据集字段(基于实际文档结构)**:
```
端(用户端/管家端/PC后台) | 章节(35 个一级标题) | 段落 | 跳转链接 | 适用语言(zh/en/vi) | 是否家充 | 地域
```

**35 个章节(从英文原版实际提取)**:
- **PC 管理后台**(16 个): Role Management / Shop Level / Individual operator / Operator review for entry / Add sites under the operator / Site audit / Billing Template (Charging Station) / Add product model / equipment / Placement equipment / Charging coupons / Equipment Failure List / User Management / Financial Management / Order Management / Operations Management / Data View
- **用户端 C 端**(9 个): Sign up / top-up / place an order / Four wheel charging order / Placeholder fee order / venue / license plate / Change password / Fault Repair
- **管家端 B 端**(10 个): Sign up / Real name authentication / Create venue / my venue / Create template / Venue association template / Placement equipment / data sector / order / Venue details / Profit withdrawal

**多语言范围(已对齐)**:
- **当前只支持 zh/en/vi 三种语言**
- 不支持的语言 → 降级到英文(并明确告知用户"已切换到英文")
- 后续拓展其他语言时,只需在 `<DATASET_OPERATION_GUIDE>` 追加对应语言的 markdown 文档,**不需改 yml**

**多语言约束(G11)**:
- 每篇操作手册文档必须包含 `language` + `endpoint` 元数据
- 5030 KR 的 query_variable_selector 用 input_language 过滤,metadata filter 锁定 endpoint
- 5031 LLM 的 prompt 头部硬编码"严格使用 {{language}} 输出,不要翻译跳转链接"

**跳转链接保留(基于操作手册实际含路由字符串)**:
- 文档中出现 `/charge/pages/placeUseFeeList/placeUseFeeList`、`/charge/pages/malfunction/malfunction` 等小程序 webview 路由
- 5032 code 节点提取这些链接,**原样输出**(前端可点击跳转)
- LLM prompt 明确禁止"翻译"或"改写"链接字符串

**验收**:
- [ ] 用户端 endpoint=user 时,只命中 C 端 9 个章节
- [ ] 管家端 endpoint=butler 时,只命中 B 端 10 个章节
- [ ] PC 后台 endpoint=pc 时,只命中 PC 端 16 个章节
- [ ] zh/en/vi 各语言均能命中对应手册
- [ ] 不支持的语言(例如 ja/fr)降级到英文,并在响应中说明
- [ ] 输出是编号步骤,不是段落
- [ ] 跳转链接字符串原样保留,不被翻译
- [ ] 新增语言时,只需在 KB 追加文档,yaml 无需修改

---

### SPEC-E1 — End 节点聚合 + SceneResponse JSON 打包 [P0]

**关闭缺口**: G9

**目标**: 把 4 路(scene A/B/C/fallback)的输出合并成 SceneResponse JSON。

**节点**:
- 5080 `variable-aggregator` — 收集 [5017.text, 5021.text, 5022.scene_response, 5031.text, 5090.scene_response]
- 5081 `code_打包SceneResponse` — 包装成 SceneResponse JSON 字符串

**打包逻辑(伪代码)**:
```python
def main(agg, scene, risk_level, confidence, structured):
    return {
        "output": json.dumps({
            "scene": scene,
            "risk_level": risk_level,
            "confidence": confidence,
            "payload": {
                "text": agg,
                "structured": structured,
                "next_actions": [...]  # 由各路径提供
            }
        }, ensure_ascii=False)
    }
```

**验收**:
- [ ] 4 路场景任一触发时,output 都是合法 JSON
- [ ] JSON 可被前端 `JSON.parse()` 直接解析
- [ ] 包含 scene / risk_level / payload.text 三个最小字段

---

### SPEC-F1 — 知识库数据补全(7 个数据集) [P1]

**关闭缺口**: G12, G13

**目标**: 创建 7 个新知识库的占位文档(可空文档,占位即可,后续由运营填充)。

**数据集清单(基于 `32-6.17` 实际资料梳理)**:

| 占位 ID | 来源资料 | 文档结构(字段) | 估计条数 |
|---------|----------|----------------|----------|
| `<DATASET_PRODUCT_SPEC>` | `趋势云-标准充电桩功能清单V2.4.1.xlsx` 8 sheet(扣除版本记录) | `板块 \| 模块 \| 功能点 \| 功能说明 \| 备注 \| 端类型(用户/管家/PC) \| 版本(V2.x) \| 是否家充 \| 地域(国内/海外)` | 200+ |
| `<DATASET_PRODUCT_CHANGELOG>` | 同上 `版本记录` sheet | `版本号 \| 更新内容 \| 更新时间 \| 编写人` | 5+ |
| `<DATASET_PRICING>` | 暂无原始资料,运营补 | `SKU \| 区域 \| 价格 \| 货币 \| 生效日期 \| 备注` | 15+ |
| `<DATASET_FAULT_DIAGNOSIS>` | 操作手册 `Equipment Failure List` + `Fault Repair` 章节 | `故障码 \| 现象 \| 可能原因 \| 排查步骤 \| 兜底建议 \| 端类型 \| 是否家充` | 25+ |
| `<DATASET_OPERATION_GUIDE>` | `Standard Operating Manual for Charging Piles.docx`(190 段) | `端(用户端/管家端/PC后台) \| 章节(35个一级标题) \| 段落 \| 跳转链接 \| 适用语言(zh/en/vi)` | 190 × 3 语言 |
| `<DATASET_FAQ>` | `常见问题解答.xlsx`(49 条) | `功能节点(21个) \| 常见疑问(中文) \| 常见疑问(英文) \| 回答(英文) \| 端类型 \| 地域 \| 是否家充` | 49+ |
| `<DATASET_I18N_FALLBACK>`(新增) | `data_processed.csv` 抽 `充电桩` 顶级菜单 | `菜单名 \| 字段key \| CN \| EN \| VI` | 2310 / 3 |

**SPEC-C1 multi_retrieval 多库一起查(已对齐)**:
- 流程1 / 流程2 检索同时覆盖 `<DATASET_PRODUCT_SPEC>` 和 `<DATASET_PRODUCT_CHANGELOG>`(权重 0.7 + 0.3)
- 路径 B 检索同时覆盖 `<DATASET_FAULT_DIAGNOSIS>` 和 `<DATASET_FAQ>`(FAQ 节点 `equipment` / `Equipment Failure List` 用作补充)
- 路径 C 检索同时覆盖 `<DATASET_OPERATION_GUIDE>` 三语言文档,加 metadata filter `[端类型=scene.端, 语言=input_language]`

**FAQ 与操作手册双向引用**:
- 21 个 FAQ 节点 与 35 个操作手册章节有 19 个直接对应(`Role Management` / `Sign up` / `Site audit` / `Billing Template` 等)
- 实现:FAQ 文档每条加 `related_manual_chapter` 字段,操作手册文档每段加 `related_faq_node` 字段,前端可在 FAQ 答案末尾显示"查看完整操作步骤 →"链接

**验收**:
- [ ] 7 个 markdown 文档存在于 `Workflow-China_charge_seriver-draft-9380/knowledge_bases/` 下
- [ ] 每个文档的字段结构符合上表
- [ ] FAQ 文档的关键词标签覆盖 21 个功能节点
- [ ] 操作手册按 35 个一级标题 + 3 端 + 3 语言切片
- [ ] 由 SPEC-H1 创建对应的 Dify KB 并替换占位 ID
- [ ] `<DATASET_I18N_FALLBACK>` 同时生成 `frontend/src/i18n/charge.csv` 副本供前端 fallback

---

### SPEC-G1 — 后端协同(ChargeSceneResponse + scene_router) [P0]

**关闭缺口**: (后端,与本工作流联合)

**目标**: 让后端能消费新工作流输出的 SceneResponse,并按 scene 路由到不同的渲染逻辑。

**交付物**:
- `backend/health_consult/schemas.py` 新增 `ChargeSceneResponse`(或新建 `backend/charge_consult/`)
- `backend/health_consult/scene_router.py` 新增 `CHARGING_SCENE_HANDLERS`
- 或新建 `backend/charge_consult/scene_router.py`(推荐,避免和健康咨询混)

**最小实现**:
```python
# schemas.py
class ChargeSceneResponse(BaseModel):
    scene: Literal["pre_sale", "after_sales", "operation", "pricing", "faq", "fallback"]
    risk_level: Literal["low", "medium", "high", "urgent"]
    confidence: float
    payload: dict

# scene_router.py
CHARGING_SCENE_HANDLERS = {
    "pre_sale": handle_pre_sale,
    "after_sales": handle_after_sales,
    "operation": handle_operation,
    "pricing": handle_pricing,
    "faq": handle_faq,         # 新增:FAQ 直查场景
    "fallback": handle_fallback,
}

# 工单 API 留 placeholder(无工单系统,后续拓展)
def create_ticket(scene_payload: dict) -> str:
    """当前 NotImplementedError,工单 API 就绪后填实现"""
    raise NotImplementedError("工单 API 尚未对接,后续拓展")
```

**危险信号关键词接口(已对齐)**:
- 后端新增 `GET /api/charge-consult/danger-keywords` 接口,返回当前生效的危险信号关键词列表
- Dify 工作流 5020 节点通过 HTTP-request 调此接口获取关键词,**不把关键词写死在 yml**
- 关键词变更只需后端更新列表 + 重启,**无需重新部署 Dify 工作流**

**验收**:
- [ ] 后端能解析新工作流 output 字段为 ChargeSceneResponse
- [ ] 各 scene handler 至少有一个空实现(stub),`faq` handler 必须直透 SceneResponse 不改写
- [ ] `create_ticket` 函数存在,调用时返回 NotImplementedError,不报错退出
- [ ] `GET /api/charge-consult/danger-keywords` 返回当前关键词列表
- [ ] 与健康咨询共用同一 envelope(`responses_to_unified`)

---

### SPEC-H1 — 部署与端到端冒烟测试 [P0]

**关闭缺口**: 全部(回归验收)

**目标**: 把 SPEC-A~G 的成果部署到 Dify prod 并跑通 4 类场景的冒烟测试。

**子步骤**:
1. 在 Dify 控制台创建 5 个新 KB(对应 SPEC-F1),记录 dataset_id
2. 用 sed 替换 yml 中的 `<DATASET_*>` 占位符(借鉴 `DEPLOY_INSTRUCTIONS.md` 步骤 5)
3. 用 dify_workflow_toolkit 的 builder + deployer 导入新 yml
4. 在 `.env.dify-consult`(或新建 `.env.dify-charge`)写入新 workflow_id 和 api_key
5. 启动后端,验证 `GET /api/charge-consult/health` 返回 ok
6. 4 类场景各跑一次 curl 冒烟测试:
   - 路径 A: "这桩有什么功能?" → scene=pre_sale
   - 路径 B: "充电突然中断,指示灯红色" → scene=after_sales, risk_level=high
   - 路径 C: "App 怎么解绑车辆" → scene=operation
   - 报价: "7kW 充电桩多少钱" → scene=pricing
7. E2E 浏览器验证(可选,H5 前端按 scene 渲染)

**验收**:
- [ ] 4 个 curl 测试都返回 200 + 合法 SceneResponse JSON
- [ ] 新 workflow_id 已写入 .env,后端服务能正常调用
- [ ] Dify 控制台工作流显示为"已发布"状态
- [ ] 旧 yml 保留可回滚(新建 `China_charge_seriver_v1_backup.yml`)

---

## 3. 执行顺序(建议)

```
Phase 1 — 设计 (SPEC-A1, A2, A3)         ← 本周可完成
   ↓
Phase 2 — 数据 (SPEC-F1)                  ← 与 Phase 1 并行,先填占位
   ↓
Phase 3 — 核心节点 (SPEC-B1, C1, C2, C3)  ← 串行,每个独立可测
   ↓
Phase 4 — 业务路径 (SPEC-D1, D2, D3)     ← 依赖 Phase 3 输出
   ↓
Phase 5 — 聚合输出 (SPEC-E1)              ← 依赖 Phase 4
   ↓
Phase 6 — 后端 (SPEC-G1)                  ← 与 Phase 5 并行
   ↓
Phase 7 — 部署验证 (SPEC-H1)              ← 最后
```

---

## 4. 验收总览(全部 SPEC 完工时)

- [ ] 架构图 7 项验收检查全部通过(见 `01_ARCHITECTURE_UNDERSTANDING.md` 第 7 节)
- [ ] 缺口对照表 15 项(G1~G15)全部关闭
- [ ] 4 类场景的 curl 冒烟测试全部通过
- [ ] 后端能解析 SceneResponse 并按 scene 路由
- [ ] 旧 yml 保留作为回滚备份
- [ ] 文档齐全:本文档 + 01/02 + 04(契约)+ 05(节点拓扑)

---

## 5. 已决策事项(2026-06-18 对齐)

| # | 决策项 | 决定 | 影响 SPEC |
|---|--------|------|-----------|
| 1 | scene_classifier 方案 | **方案 Z — code + LLM 混合**,FAQ 走知识库固定答案跳过 LLM | B1 |
| 2 | 多语言范围 | **当前只支持 zh/en/vi**,后续拓展 | D3、F1 |
| 3 | 危险信号关键词维护 | **由后端维护**,Dify 通过 HTTP 节点动态拉取,不写死 yml | D2、G1 |
| 4 | 工单 API 对接 | **当前无工单 API**,`create_ticket` 留 placeholder,后续拓展 | D2、G1 |
| 5 | 跨文档检索策略 | **multi_retrieval 多库一起查**,weights + reranking | C1、C2、D1、D2、D3 |

---

## 6. 遗留风险(尚未决策,可能在施工中发现)

- [ ] 路径 B 紧急场景(漏电/冒烟)的兜底回复,文字内容是否需要法律/合规审核?
- [ ] 报价库的"区域"维度如何切分(国家?渠道?经销商级别?)
- [ ] FAQ 标签维护流程由谁负责,如何和现有知识库协同?
- [ ] 多渠道(H5 / App / 微信 / 邮件)接入时,scene 分类是否一致,还是要按渠道微调?