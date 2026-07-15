"""Pydantic models — charge_consult 模块的 4 维分类契约。

本文件是 SPEC-A1 的施工产物,把以下 4 维分类落到 schema:
  1. scene      — 业务意图 (pre_sale / after_sales / operation / pricing / faq / fallback)
  2. endpoint   — 端类型   (user / butler / pc) — 从关键词 + language 推断
  3. region     — 地域     (cn / overseas)      — 海外独有谷歌/脸书
  4. pile_type  — 桩型     (public / home)      — V2.4 新增家充

JSON 契约与 `frontend/src/data/charge.ts` 严格对齐,
供 Agent 1 (Dify 工作流) 和 Agent 3 (前端) 共同遵守。

参考: `backend/health_consult/schemas.py` 的 SceneResponse 模式。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── 4 维分类枚举 ────────────────────────────────────────────────
# 注意: 顺序即优先级,前者在代码节点关键词匹配时优先命中
CHARGE_SCENE_ENUMS = (
    "pre_sale",      # 售前咨询 — 这桩有什么功能?能不能定时充电?
    "after_sales",   # 售后 — 充电中断、漏电、跳闸、退款、投诉
    "operation",     # 操作指导 — App/H5/PC 后台/管家端 步骤化指引
    "pricing",       # 报价 — 产品/配件/服务价格
    "faq",           # FAQ 直查 — 命中 21 个功能节点标签时走 KB 固定答案
    "fallback",      # 兜底 — 无法识别时降级,返回"请补充描述"
)

CHARGE_ENDPOINT_ENUMS = (
    "user",          # C 端用户(用户端 App/H5/小程序)
    "butler",        # B 端运营商(管家端)
    "pc",            # 平台管理员(PC 后台)
)

CHARGE_REGION_ENUMS = (
    "cn",            # 国内 — 默认
    "overseas",      # 海外 — 关键词触发: google/谷歌/facebook/脸书/overseas
)

CHARGE_PILE_TYPE_ENUMS = (
    "public",        # 公共充电桩 — 默认
    "home",          # 家充(V2.4+ 新增) — 关键词: 家充/家用/私人桩
)

CHARGE_RISK_ENUMS = (
    "low",           # 正常 — 默认
    "medium",        # 提示
    "high",          # 重要 — 需立即关注
    "urgent",        # 危险 — 漏电/冒烟/跳闸后无法复位等,触发硬闸门
)


# 类型别名,供其他模块 import
ChargeScene = Literal["pre_sale", "after_sales", "operation", "pricing", "faq", "fallback"]
ChargeEndpoint = Literal["user", "butler", "pc"]
ChargeRegion = Literal["cn", "overseas"]
ChargePileType = Literal["public", "home"]
ChargeRiskLevel = Literal["low", "medium", "high", "urgent"]


# ── 危险信号结构 ────────────────────────────────────────────────
class ChargeDangerSignal(BaseModel):
    """单条危险信号关键词配置(由后端维护,MVP 写死,后续从 CMS 拉)。"""

    keyword: str = Field(..., min_length=1, max_length=64, description="匹配关键词")
    endpoint: ChargeEndpoint = Field(..., description="端类型 — 该关键词在哪一端会触发")
    risk_level: ChargeRiskLevel = Field(default="urgent", description="命中后的风险等级")
    action: str = Field(..., min_length=1, max_length=128, description="建议动作,如 '立即停用并联系售后'")


class ChargeDangerSignalHit(BaseModel):
    """危险信号命中结果(代码节点输出,前端按此渲染红色警示条)。"""

    matched: bool = False
    keyword: Optional[str] = None
    risk_level: ChargeRiskLevel = "low"
    action: Optional[str] = None
    endpoint: Optional[ChargeEndpoint] = None
    # 兜底建议文字,前端直接展示
    fallback_message: Optional[str] = None


class DangerSignalsConfig(BaseModel):
    """危险信号配置集合(由后端维护)。"""

    signals: list[ChargeDangerSignal] = Field(default_factory=list)
    last_updated: str = Field(..., description="ISO8601 时间戳,前端可提示'配置已过期'")
    version: str = Field(default="0.1.0", description="配置版本号")


# ── FAQ 命中结构 ────────────────────────────────────────────────
class ChargeFaqHit(BaseModel):
    """FAQ 直查命中结果(SPEC-B1 5002-2 节点输出)。"""

    matched: bool = False
    node: Optional[str] = Field(None, description="21 个功能节点之一,与 `常见问题解答.xlsx` 一致")
    question: Optional[str] = None
    answer: Optional[str] = None
    # 与文档原文的 hash,前端可做"答案未被人为篡改"校验
    answer_hash: Optional[str] = None
    related_manual_chapter: Optional[str] = Field(
        None, description="关联到操作手册的 35 个一级标题(便于跳转)"
    )


# ── Next actions ────────────────────────────────────────────────
class NextAction(BaseModel):
    """前端按钮 / 跳转建议(SPEC-D2 兜底 G15 用)。"""

    type: Literal["call_support", "open_url", "show_steps", "create_ticket"]
    label: str = Field(..., min_length=1, max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)
    # create_ticket 后续拓展(SPEC-G1 留 placeholder,当前 Dify 无工单 API)
    is_implemented: bool = Field(default=True, description="若 False,前端要降级为 'TODO 文本'")


# ── 业务输出 payload ────────────────────────────────────────────
class ChargePayload(BaseModel):
    """SceneResponse.payload — 业务内容,scene 不同结构不同。

    统一字段:
      - text:          主回复文字(LLM 生成 / FAQ 原文 / 兜底文案)
      - flow_results:  后台三流(流程1/2/3)的预检结果
      - faq:           FAQ 命中详情(scene=faq 时非空)
      - danger:        危险信号命中详情(scene=after_sales 时非空)
      - manual:        操作手册片段(scene=operation 时非空,含跳转链接)
      - pricing_table: 报价结构化输出(scene=pricing 时非空)
      - next_actions:  前端按钮 / 跳转建议
    """

    text: str = Field(..., min_length=0, max_length=4000)

    # 后台三流预检(SPEC-C1/C2/C3)
    flow1_matched: Optional[bool] = Field(None, description="流程1 — 功能是否覆盖")
    flow2_verified: Optional[bool] = Field(None, description="流程2 — 清单是否准确")
    flow3_pricing: Optional[str] = Field(None, description="流程3 — 报价原文(MVP 字符串)")

    # 业务细节
    faq: ChargeFaqHit = Field(default_factory=ChargeFaqHit)
    danger: ChargeDangerSignalHit = Field(default_factory=ChargeDangerSignalHit)
    manual: dict[str, Any] = Field(
        default_factory=dict,
        description="scene=operation 时填充,含 chapter / steps / deep_link / language",
    )
    pricing_table: list[dict[str, Any]] = Field(
        default_factory=list,
        description="scene=pricing 时填充,每行 {sku, region, price, currency, valid_until}",
    )

    # 行动建议
    next_actions: list[NextAction] = Field(default_factory=list)

    # 调试
    matched_function: Optional[str] = Field(None, description="命中功能点名称,如 '定时充电'")
    matched_version: Optional[str] = Field(None, description="命中功能点版本,如 'V2.4'")


# ── 4 维 SceneResponse 主体 ──────────────────────────────────────
class ChargeSceneResponse(BaseModel):
    """End 节点输出的统一契约(SPEC-A1)。

    4 维分类:
      - scene:      业务意图
      - endpoint:   端类型
      - region:     地域
      - pile_type:  桩型

    风险:
      - risk_level:  风险等级
      - confidence:  置信度(本地兜底时 < 0.7,Dify 正常时 ≥ 0.9)

    输出:
      - payload:     业务内容
      - raw:         原始 Dify 响应(可选,前端调试用)
    """

    scene: ChargeScene
    endpoint: ChargeEndpoint = "user"
    region: ChargeRegion = "cn"
    pile_type: ChargePileType = "public"
    risk_level: ChargeRiskLevel = "low"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    payload: ChargePayload
    # 原始 Dify 响应(可选,前端调试 / 后端日志)
    raw: Optional[dict[str, Any]] = None
    # 路由元数据(本地兜底时填 'local_fallback',Dify 正常时填 workflow_id)
    source: Literal["dify", "local_fallback", "hybrid"] = "dify"
    # 时间戳 ISO8601
    ts: str = Field(..., description="ISO8601 UTC 时间戳")


# ── API 请求表单(MVP: FastAPI Form 字段) ──────────────────────
class ChargeChatRequest(BaseModel):
    """文档化表单字段,实际用 FastAPI Form() 在 endpoint 处接收。

    文件(image / audio)通过 UploadFile 单独接收,不在 Pydantic 模型里。
    """

    text: str = Field(default="", max_length=4000)
    answers: str = Field(default="", description="多问卷的 JSON 字符串(scene=operation 时用)")
    session_id: str = Field(default="", description="会话 ID,后端 Redis 存上下文")
    turn: int = Field(default=1, ge=1, le=20, description="轮次,1=第一轮,2+=后续轮次")
    language: Literal["zh", "en", "vi"] = Field(default="zh", description="用户语言 — 影响 region / 路径 C 输出")
    # 上下文(上一轮三流结果,后端从 Redis 读后注入,前端不必传)
    context_json: str = Field(default="", description="上一轮 {flow1, flow2, flow3} 序列化")
    # 端类型提示(可选,前端可以告知,后端也可从 UA / channel 推断)
    hint_endpoint: Optional[ChargeEndpoint] = None
    hint_region: Optional[ChargeRegion] = None


# ── 运维用 schema(health/version) ────────────────────────────────
class HealthResponse(BaseModel):
    """健康检查 — /api/charge-consult/health。"""

    status: str = Field(default="ok", description="固定 ok")
    service: str = Field(..., description="服务名,来自 settings.app_name")
    version: str = Field(..., description="版本号,来自 settings.app_version")


class VersionResponse(BaseModel):
    """版本信息 — /api/charge-consult/version。"""

    version: str = Field(..., description="服务版本号")
    dify_workflow_id: str = Field(..., description="绑定的 Dify workflow_id")
