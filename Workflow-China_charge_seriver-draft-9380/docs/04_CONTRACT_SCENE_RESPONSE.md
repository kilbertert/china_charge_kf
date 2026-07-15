# ChargeSceneResponse 4 维分类契约 — SPEC-A1

> 状态: ✅ 已施工完成,54/54 测试通过
> 关联代码: `backend/charge_consult/{schemas,scene_router,danger_signals}.py`
> 关联测试: `backend/charge_consult/tests/test_charge_schema.py`
> 关联 SPEC: `docs/03_REFACTOR_SPEC.md` § SPEC-A1 / B1 / D2 / G1

---

## 1. 设计目标

定义 End 节点输出的统一 JSON 结构,把 **4 维分类** (scene / endpoint / region / pile_type) 落到 schema,供:

- **后端**: `ChargeSceneResponse` Pydantic 模型解析 Dify workflow 输出
- **前端**: TypeScript type 强校验,按 scene + endpoint 渲染不同 UI
- **Dify yml**: `5081 code_打包SceneResponse` 节点按此 schema 输出 JSON
- **测试**: 54 个 pytest 用例覆盖 4 维 + 危险信号 + FAQ + 兜底路径

---

## 2. 4 维分类定义

| 维度 | 字段 | 取值 | 决策依据 |
|------|------|------|----------|
| 业务意图 | `scene` | `pre_sale` / `after_sales` / `operation` / `pricing` / `faq` / `fallback` | 关键词优先 + LLM 兜底 |
| 端类型 | `endpoint` | `user` / `butler` / `pc` | 关键词 + 前端 hint |
| 地域 | `region` | `cn` / `overseas` | `language` 变量 + 关键词 |
| 桩型 | `pile_type` | `public` / `home` | 关键词(家充/家用/私人桩) |

### 2.1 分类优先级(关键!)

scene 字段的判定必须按以下顺序,**危险信号永远先于 FAQ**:

```
1. 危险信号(后端维护,SPEC-D2 5020)
   ↓
2. 报价关键词
   ↓
3. FAQ 节点命中(SPEC-B1 5002-2)
   ↓
4. 售后关键词
   ↓
5. 售前关键词
   ↓
6. fallback(无法识别)
```

⚠️ **反例**: 如果不把危险信号放第一,用户问"Equipment Failure"会先被 FAQ 节点"Equipment Failure List"命中,导致错过安全告警。

---

## 3. Pydantic Schema(Python 端)

### 3.1 枚举类型

```python
CHARGE_SCENE_ENUMS    = ("pre_sale", "after_sales", "operation", "pricing", "faq", "fallback")
CHARGE_ENDPOINT_ENUMS = ("user", "butler", "pc")
CHARGE_REGION_ENUMS   = ("cn", "overseas")
CHARGE_PILE_TYPE_ENUMS = ("public", "home")
CHARGE_RISK_ENUMS     = ("low", "medium", "high", "urgent")
```

### 3.2 主体模型 `ChargeSceneResponse`

```python
class ChargeSceneResponse(BaseModel):
    scene: ChargeScene                          # 必填
    endpoint: ChargeEndpoint = "user"            # 默认 user
    region: ChargeRegion = "cn"                  # 默认 cn
    pile_type: ChargePileType = "public"         # 默认 public
    risk_level: ChargeRiskLevel = "low"          # 默认 low
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)  # [0, 1]
    payload: ChargePayload                      # 必填
    raw: Optional[dict[str, Any]] = None
    source: Literal["dify", "local_fallback", "hybrid"] = "dify"
    ts: str                                      # 必填, ISO8601 UTC
```

### 3.3 嵌套结构

```
ChargeSceneResponse
├── scene / endpoint / region / pile_type / risk_level / confidence
├── source (dify | local_fallback | hybrid)
├── ts (ISO8601)
└── payload: ChargePayload
    ├── text: str                                # 主回复文字
    ├── flow1_matched: Optional[bool]            # 流程1 — 功能是否覆盖
    ├── flow2_verified: Optional[bool]           # 流程2 — 清单是否准确
    ├── flow3_pricing: Optional[str]             # 流程3 — 报价原文
    ├── faq: ChargeFaqHit                        # FAQ 命中详情
    │   ├── matched: bool
    │   ├── node: Optional[str]                  # 21 节点之一
    │   ├── question / answer
    │   ├── answer_hash: Optional[str]           # 防篡改校验
    │   └── related_manual_chapter: Optional[str]  # 关联手册章节
    ├── danger: ChargeDangerSignalHit            # 危险信号命中详情
    │   ├── matched: bool
    │   ├── keyword / risk_level / action / endpoint
    │   └── fallback_message: Optional[str]
    ├── manual: dict                             # 路径C 操作手册片段
    │   ├── chapter: str                         # 35 一级标题之一
    │   ├── steps: list[str]                     # 步骤列表
    │   ├── deep_link: str                       # /charge/pages/...
    │   └── language: str                        # zh / en / vi
    ├── pricing_table: list[dict]                # 路径D 报价结构化
    │   └── {sku, region, price, currency, valid_until}
    ├── next_actions: list[NextAction]
    │   ├── type: call_support | open_url | show_steps | create_ticket
    │   ├── label: str
    │   ├── payload: dict
    │   └── is_implemented: bool                 # create_ticket 当前 False
    ├── matched_function: Optional[str]          # 命中功能点
    └── matched_version: Optional[str]           # 命中功能点版本
```

---

## 4. JSON Schema(JSON 端)

> 前端直接 `JSON.parse` 即可,无需再做字段映射。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["scene", "payload", "ts"],
  "properties": {
    "scene": {
      "type": "string",
      "enum": ["pre_sale", "after_sales", "operation", "pricing", "faq", "fallback"]
    },
    "endpoint": {
      "type": "string",
      "enum": ["user", "butler", "pc"],
      "default": "user"
    },
    "region": {
      "type": "string",
      "enum": ["cn", "overseas"],
      "default": "cn"
    },
    "pile_type": {
      "type": "string",
      "enum": ["public", "home"],
      "default": "public"
    },
    "risk_level": {
      "type": "string",
      "enum": ["low", "medium", "high", "urgent"],
      "default": "low"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 1.0
    },
    "source": {
      "type": "string",
      "enum": ["dify", "local_fallback", "hybrid"],
      "default": "dify"
    },
    "ts": {
      "type": "string",
      "format": "date-time",
      "description": "ISO8601 UTC timestamp"
    },
    "payload": {
      "type": "object",
      "required": ["text"],
      "properties": {
        "text": { "type": "string", "maxLength": 4000 },
        "flow1_matched": { "type": ["boolean", "null"] },
        "flow2_verified": { "type": ["boolean", "null"] },
        "flow3_pricing": { "type": ["string", "null"] },
        "faq": { "$ref": "#/$defs/ChargeFaqHit" },
        "danger": { "$ref": "#/$defs/ChargeDangerSignalHit" },
        "manual": { "type": "object" },
        "pricing_table": { "type": "array" },
        "next_actions": { "type": "array" },
        "matched_function": { "type": ["string", "null"] },
        "matched_version": { "type": ["string", "null"] }
      }
    }
  },
  "$defs": {
    "ChargeFaqHit": {
      "type": "object",
      "properties": {
        "matched": { "type": "boolean" },
        "node": { "type": ["string", "null"] },
        "question": { "type": ["string", "null"] },
        "answer": { "type": ["string", "null"] },
        "answer_hash": { "type": ["string", "null"] },
        "related_manual_chapter": { "type": ["string", "null"] }
      }
    },
    "ChargeDangerSignalHit": {
      "type": "object",
      "properties": {
        "matched": { "type": "boolean" },
        "keyword": { "type": ["string", "null"] },
        "risk_level": { "type": "string" },
        "action": { "type": ["string", "null"] },
        "endpoint": { "type": ["string", "null"] },
        "fallback_message": { "type": ["string", "null"] }
      }
    }
  }
}
```

---

## 5. TypeScript 类型(前端端)

```typescript
// frontend/src/types/charge.ts

export type ChargeScene = 'pre_sale' | 'after_sales' | 'operation' | 'pricing' | 'faq' | 'fallback';
export type ChargeEndpoint = 'user' | 'butler' | 'pc';
export type ChargeRegion = 'cn' | 'overseas';
export type ChargePileType = 'public' | 'home';
export type ChargeRiskLevel = 'low' | 'medium' | 'high' | 'urgent';
export type ChargeSource = 'dify' | 'local_fallback' | 'hybrid';

export interface ChargeFaqHit {
  matched: boolean;
  node?: string;
  question?: string;
  answer?: string;
  answer_hash?: string;
  related_manual_chapter?: string;
}

export interface ChargeDangerSignalHit {
  matched: boolean;
  keyword?: string;
  risk_level: ChargeRiskLevel;
  action?: string;
  endpoint?: ChargeEndpoint;
  fallback_message?: string;
}

export interface ChargeManualFragment {
  chapter: string;
  steps: string[];
  deep_link: string;
  language: 'zh' | 'en' | 'vi';
}

export interface ChargePricingRow {
  sku: string;
  region: string;
  price: string;
  currency: string;
  valid_until: string;
}

export interface ChargeNextAction {
  type: 'call_support' | 'open_url' | 'show_steps' | 'create_ticket';
  label: string;
  payload: Record<string, unknown>;
  is_implemented: boolean;
}

export interface ChargePayload {
  text: string;
  flow1_matched?: boolean | null;
  flow2_verified?: boolean | null;
  flow3_pricing?: string | null;
  faq: ChargeFaqHit;
  danger: ChargeDangerSignalHit;
  manual: Partial<ChargeManualFragment>;
  pricing_table: ChargePricingRow[];
  next_actions: ChargeNextAction[];
  matched_function?: string;
  matched_version?: string;
}

export interface ChargeSceneResponse {
  scene: ChargeScene;
  endpoint: ChargeEndpoint;
  region: ChargeRegion;
  pile_type: ChargePileType;
  risk_level: ChargeRiskLevel;
  confidence: number;
  source: ChargeSource;
  ts: string;
  payload: ChargePayload;
  raw?: Record<string, unknown>;
}
```

---

## 6. 端到端冒烟用例(SPEC-H1 用)

### 6.1 售前(pre_sale)

```bash
curl -X POST http://localhost:8013/api/charge-consult/chat \
  -F "text=这桩有什么功能?" \
  -F "session_id=test-pre-sale"
```

期望:
```json
{
  "scene": "pre_sale",
  "endpoint": "user",
  "region": "cn",
  "pile_type": "public",
  "risk_level": "low",
  "confidence": 0.9,
  "source": "dify",
  "ts": "2026-06-18T...",
  "payload": {
    "text": "...",
    "flow1_matched": true,
    "next_actions": [{"type": "show_steps", "label": "查看详情", ...}]
  }
}
```

### 6.2 售后危险信号(after_sales + urgent)

```bash
curl -X POST http://localhost:8013/api/charge-consult/chat \
  -F "text=我的桩漏电了,跳闸后无法复位" \
  -F "session_id=test-danger"
```

期望:
```json
{
  "scene": "after_sales",
  "risk_level": "urgent",
  "confidence": 1.0,
  "payload": {
    "text": "⚠️ 检测到危险信号: 漏电。建议: 立即停止充电...",
    "danger": {
      "matched": true,
      "keyword": "漏电",
      "risk_level": "urgent",
      "endpoint": "user",
      "fallback_message": "⚠️ 检测到危险信号: 漏电..."
    },
    "next_actions": [{"type": "call_support", "label": "联系售后", ...}]
  }
}
```

### 6.3 FAQ 直查(faq)

```bash
curl -X POST http://localhost:8013/api/charge-consult/chat \
  -F "text=Role Management 权限怎么分配?" \
  -F "session_id=test-faq"
```

期望:
```json
{
  "scene": "faq",
  "endpoint": "pc",
  "confidence": 1.0,
  "payload": {
    "text": "(本地兜底) 命中 FAQ 节点: Role Management。",
    "faq": {
      "matched": true,
      "node": "Role Management",
      "related_manual_chapter": "Role Management"
    }
  }
}
```

### 6.4 报价(pricing)

```bash
curl -X POST http://localhost:8013/api/charge-consult/chat \
  -F "text=7kW 充电桩多少钱?" \
  -F "session_id=test-pricing"
```

期望:
```json
{
  "scene": "pricing",
  "risk_level": "low",
  "payload": {
    "text": "...",
    "flow3_pricing": "...",
    "pricing_table": [{"sku": "...", "region": "CN", "price": "..."}]
  }
}
```

### 6.5 海外(overseas)

```bash
curl -X POST http://localhost:8013/api/charge-consult/chat \
  -F "text=How to use Google login?" \
  -F "session_id=test-overseas" \
  -F "language=en"
```

期望 `region=overseas`,`endpoint=user`。

### 6.6 家充(home)

```bash
curl -X POST http://localhost:8013/api/charge-consult/chat \
  -F "text=家充桩怎么用?" \
  -F "session_id=test-home"
```

期望 `pile_type=home`。

---

## 7. 测试覆盖

`backend/charge_consult/tests/test_charge_schema.py` 共 54 个用例:

| 测试类 | 覆盖范围 | 用例数 |
|--------|----------|--------|
| `TestEnums` | 5 个枚举值各枚举数与值集合 | 5 |
| `TestChargeSceneResponse` | 必填字段、confidence 区间、默认值、JSON 可逆 | 5 |
| `TestClassify4D` | 4 维分类各分支: 售前/报价/售后/FAQ/空文本/endpoint 3 端/region 2 类/pile_type 2 类/hint 覆盖 | 15 |
| `TestDangerSignals` | 3 端危险信号、端隔离、不命中、空文本 | 6 |
| `TestFaqLookup` | 21 节点命中、中英双向、显式传参、关联手册章节、不命中 | 5 |
| `TestBuildLocalFallback` | 4 维兜底、危险信号升级 risk、FAQ 兜底、家充、海外、空文本、时间戳 | 7 |
| `TestChargeChatRequest` | 默认参数、turn 范围、language 限制、text 长度限制 | 4 |
| `TestEndToEnd4D` (parametrize) | 7 个端到端典型场景 | 7 |
| **合计** | | **54** |

跑测命令:
```bash
cd backend && python -m pytest charge_consult/tests/test_charge_schema.py -v
```

---

## 8. 与 SPEC-G1 后端协同

后续 SPEC-G1 阶段,FastAPI 端点 `POST /api/charge-consult/chat` 将:

1. 接收 `ChargeChatRequest` 表单(text / answers / session_id / turn / language)
2. 调用 Dify workflow(节点 ID 5001-5099)
3. 解析 Dify 输出 `output` 字段 → `ChargeSceneResponse`
4. 失败时调用 `charge_consult.scene_router.build_local_fallback()` 返回
5. 包装成统一 envelope 返回前端

envelope 格式(与 `health_consult.responses_to_unified` 对齐):
```json
{
  "status": "ok",
  "data": <ChargeSceneResponse>,
  "ts": "2026-06-18T...",
  "request_id": "..."
}
```

---

## 9. 决策记录

| 决策 | 理由 | 替代方案 |
|------|------|----------|
| 危险信号先于 FAQ | 安全告警永远优先,不能被知识查询覆盖 | A. 拆双知识库;B. 强制 LLM 二次确认 |
| 端类型分 3 组 | PC/用户/管家 关键词和知识库切片完全不同 | 合并为单组,损失精确度 |
| pile_type=home 默认 public | 兼容 V2.4 前的桩型,渐进式识别 | 默认 home,会过度识别 |
| `source` 字段区分 dify/local_fallback | 前端可提示"本地兜底,建议刷新重试" | 隐藏,只暴露 confidence |
| `confidence` 区间 [0, 1] | 业内标准,前端可做 UI 提示(< 0.7 灰色) | 0-100 整数,反人类 |
| `danger` 独立字段 | 安全告警必须显眼,不可埋在 payload 里 | 合并到 payload,前端易漏检 |
| FAQ 21 节点 + 手册 35 章节互引 | 知识图谱双向引用,前端可做"相关文档"卡片 | 各管各的,体验差 |

---

## 10. 后续 SPEC 引用

- **SPEC-B1**: scene_classifier 节点实现(Dify yml) — 必须按本契约的 4 维字段输出
- **SPEC-D2**: 危险信号判定节点(5020) — 必须从 `GET /api/charge-consult/danger-keywords?endpoint=X` 拉取配置
- **SPEC-D3**: 操作手册路径 C 输出 — `manual: {chapter, steps, deep_link, language}`
- **SPEC-F1**: 7 个数据集 — FAQ 21 节点 + 手册 35 章节作为元数据索引
- **SPEC-G1**: FastAPI 端点 + Dify proxy — 用本契约的 `ChargeSceneResponse` parse 输出
- **SPEC-H1**: 4 类场景冒烟测试 — 按第 6 节用例

---

## 11. 变更日志

| 日期 | 变更 | 负责人 |
|------|------|--------|
| 2026-06-18 | 初版,SPEC-A1 4 维分类落 schema,54/54 测试通过 | (本会话) |
