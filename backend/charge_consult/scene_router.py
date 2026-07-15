"""4 维分类本地兜底 — SPEC-B1 + SPEC-D2 的 Python 实现。

当 Dify 调用失败时,本模块用纯关键词匹配继续提供可用响应。
置信度 confidence 字段用于告诉前端"本地兜底了,用户可考虑重试"。

4 维分类逻辑:
  1. scene     — 业务意图 (6 个枚举)
  2. endpoint  — 端类型   (3 个枚举)
  3. region    — 地域     (2 个枚举)
  4. pile_type — 桩型     (2 个枚举)

参考: `backend/health_consult/scene_router.py` 的实现模式。
"""

from __future__ import annotations

import re
from typing import Optional

from charge_consult.danger_signals import get_danger_signals
from charge_consult.schemas import (
    CHARGE_ENDPOINT_ENUMS,
    CHARGE_PILE_TYPE_ENUMS,
    CHARGE_REGION_ENUMS,
    CHARGE_RISK_ENUMS,
    CHARGE_SCENE_ENUMS,
    ChargeDangerSignalHit,
    ChargeEndpoint,
    ChargeFaqHit,
    ChargePileType,
    ChargeRegion,
    ChargeRiskLevel,
    ChargeScene,
    ChargeSceneResponse,
    NextAction,
)


# ── 场景关键词(按优先级排列,前命中者胜) ─────────────────────
_FAQ_NODES = (
    # 21 个功能节点标签,与 `常见问题解答.xlsx` 严格对齐
    "Role Management", "Shop Level", "Individual operator",
    "Operator review for entry", "Add sites under the operator", "Site audit",
    "Billing Template", "Charging Order", "Charging coupons", "Create venue",
    "Data View", "Data sector", "Equipment Failure List", "Financial Management",
    "Operations Management", "Order Management", "Placement equipment",
    "Real name authentication", "Sign up", "Venue", "Venue association template",
    "equipment", "place an order", "top-up",
)

# 中文 → FAQ node 反向映射(便于中文用户也命中 FAQ)
_FAQ_NODE_ZH_HINTS: dict[str, str] = {
    "角色管理": "Role Management",
    "店铺等级": "Shop Level",
    "运营商": "Individual operator",
    "运营商审核": "Operator review for entry",
    "添加站点": "Add sites under the operator",
    "站点审核": "Site audit",
    "计费模板": "Billing Template",
    "充电订单": "Charging Order",
    "优惠券": "Charging coupons",
    "创建站点": "Create venue",
    "数据看板": "Data View",
    "数据板块": "Data sector",
    "设备故障": "Equipment Failure List",
    "财务管理": "Financial Management",
    "运营管理": "Operations Management",
    "订单管理": "Order Management",
    "投放设备": "Placement equipment",
    "实名认证": "Real name authentication",
    "注册": "Sign up",
    "场地": "Venue",
    "场地模板": "Venue association template",
    "设备": "equipment",
    "下单": "place an order",
    "充值": "top-up",
}


# 售前咨询 — 关键词相对模糊,可能落到 FAQ
_PRESALE_KEYWORDS = (
    "怎么买", "哪里买", "多少钱", "价格", "报价",
    "保修", "保修期", "质保",
    "功能", "有什么功能", "支持哪些", "能不能",
    "型号", "规格", "参数",
)

# 售后 — 设备故障 / 流程问题
_AFTER_SALES_KEYWORDS = (
    "坏了", "不工作", "不能用", "故障", "维修", "修一下",
    "退款", "退钱", "投诉", "没用", "没用过",
    "充电中断", "充不上", "充不进去",
    "漏电", "触电", "冒烟", "起火", "火花", "烧焦", "异味", "跳闸",
)

# 操作指导 — App/H5/PC/管家端 步骤化指引
_OPERATION_KEYWORDS = (
    "操作", "怎么操作", "怎么用", "怎么使用", "如何使用", "使用说明", "使用步骤",
    "操作指南", "操作步骤", "操作指导",
    "扫码充电", "启动充电", "停止充电", "开票", "退款操作", "订单操作",
    "how to use", "how to operate", "how to charge",
)

# 报价 — 明确问价
_PRICING_KEYWORDS = (
    "多少钱", "价格", "报价", "价位", "费用", "收费",
    "7kw", "7kW", "11kw", "11kW", "21kw", "21kW",
    "充电桩多少钱", "充电枪", "线缆", "配件",
)


# ── 端类型关键词 ─────────────────────────────────────────────
_ENDPOINT_USER_HINTS = (
    "app", "App", "APP", "h5", "H5", "小程序", "用户端", "客户端",
    "我", "我的", "我的桩", "我的车", "我的订单",
)
_ENDPOINT_BUTLER_HINTS = (
    "管家", "管家端", "运营", "运营商", "我的场地", "我的电站",
    "分润", "结算", "提现",
)
_ENDPOINT_PC_HINTS = (
    "后台", "PC", "pc", "管理后台", "平台",
    "站点审核", "运营商审核", "退款审核", "充值审核",
    "权限", "角色", "角色管理", "系统配置", "操作日志",
    # PC 端 danger signal 高频词(帮助 endpoint 推断)
    "Equipment Failure", "Abnormal Charging", "Abnormal",
    "退款", "故障列表", "充值审核", "财务",
)


# ── 地域关键词 ────────────────────────────────────────────────
_REGION_OVERSEAS_HINTS = (
    "overseas", "海外", "谷歌", "google", "Google", "GOOGLE",
    "脸书", "facebook", "Facebook", "FACEBOOK",
    "邮箱注册", "邮箱登录",
)


# ── 桩型关键词 ────────────────────────────────────────────────
_PILE_TYPE_HOME_HINTS = (
    "家充", "家充桩", "家用", "私人桩", "私桩", "家庭桩",
    "home charger", "home", "Home",
)


# ── 工具函数 ──────────────────────────────────────────────────
def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    """文本中是否包含任一关键词(大小写不敏感)。"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _find_faq_node(text: str) -> Optional[str]:
    """识别 FAQ 节点(优先匹配英文,其次匹配中文反向映射)。"""
    text_lower = text.lower()
    for node in _FAQ_NODES:
        if node.lower() in text_lower:
            return node
    for zh, node in _FAQ_NODE_ZH_HINTS.items():
        if zh in text:  # 中文按原样匹配
            return node
    return None


# ── 主分类函数 ────────────────────────────────────────────────
def classify_4d(
    text: str,
    language: str = "zh",
    hint_endpoint: Optional[str] = None,
    hint_region: Optional[str] = None,
) -> tuple[ChargeScene, ChargeEndpoint, ChargeRegion, ChargePileType, float]:
    """4 维分类 — 返回 (scene, endpoint, region, pile_type, confidence)。

    优先级:
      1. FAQ 关键词命中 → scene=faq(高置信度)
      2. 报价关键词命中 → scene=pricing
      3. 售后危险关键词 → scene=after_sales
      4. 售前关键词 → scene=pre_sale
      5. 模糊 → scene=fallback(低置信度)

    endpoint/region/pile_type 独立判定,可被 hint_* 覆盖。
    """
    if not text or not text.strip():
        return "fallback", "user", "cn", "public", 0.3

    # ── 1. 先确定 endpoint(后面 danger signal 判定要用) ──
    endpoint: ChargeEndpoint
    if hint_endpoint in CHARGE_ENDPOINT_ENUMS:
        endpoint = hint_endpoint  # type: ignore[assignment]
    elif _has_any(text, _ENDPOINT_PC_HINTS):
        endpoint = "pc"
    elif _has_any(text, _ENDPOINT_BUTLER_HINTS):
        endpoint = "butler"
    else:
        endpoint = "user"

    # ── 2. region(hint 优先,否则启发式) ──
    region: ChargeRegion
    if hint_region in CHARGE_REGION_ENUMS:
        region = hint_region  # type: ignore[assignment]
    elif language == "en" or _has_any(text, _REGION_OVERSEAS_HINTS):
        region = "overseas"
    else:
        region = "cn"

    # ── 3. pile_type ──
    pile_type: ChargePileType = "home" if _has_any(text, _PILE_TYPE_HOME_HINTS) else "public"

    # ── 4. scene(优先级: 危险信号 > 报价 > FAQ > 售后 > 售前 > fallback) ──
    # 关键: 危险信号必须先于 FAQ 判定
    #   (例如 "Equipment Failure" 同时是 FAQ 节点名,也是 PC 端危险信号词)
    #   危险语义优先,FAQ 是知识性查询不应覆盖安全告警
    scene: ChargeScene
    confidence = 1.0
    danger_signals = get_danger_signals(endpoint)
    text_lower = text.lower()
    has_danger = any(sig.keyword.lower() in text_lower for sig in danger_signals)
    faq_node = _find_faq_node(text)

    if has_danger:
        scene = "after_sales"
        confidence = 1.0
    elif _has_any(text, _PRICING_KEYWORDS):
        scene = "pricing"
        confidence = 0.95
    elif faq_node:
        scene = "faq"
        confidence = 1.0
    elif _has_any(text, _AFTER_SALES_KEYWORDS):
        scene = "after_sales"
        confidence = 0.95
    elif _has_any(text, _OPERATION_KEYWORDS):
        scene = "operation"
        confidence = 0.9
    elif _has_any(text, _PRESALE_KEYWORDS):
        scene = "pre_sale"
        confidence = 0.9
    else:
        scene = "fallback"
        confidence = 0.5

    return scene, endpoint, region, pile_type, confidence


# ── 危险信号匹配 ─────────────────────────────────────────────
def match_danger_signals(
    text: str, endpoint: ChargeEndpoint = "user"
) -> ChargeDangerSignalHit:
    """匹配危险信号 — 命中第一条即返回。"""
    if not text:
        return ChargeDangerSignalHit()
    signals = get_danger_signals(endpoint)
    for sig in signals:
        if sig.keyword.lower() in text.lower():
            return ChargeDangerSignalHit(
                matched=True,
                keyword=sig.keyword,
                risk_level=sig.risk_level,
                action=sig.action,
                endpoint=sig.endpoint,
                fallback_message=(
                    f"⚠️ 检测到危险信号: {sig.keyword}。"
                    f"建议: {sig.action}。"
                ),
            )
    return ChargeDangerSignalHit()


# ── FAQ 直查占位(后续从 KB 拉) ───────────────────────────────
def lookup_faq(text: str, node: Optional[str] = None) -> ChargeFaqHit:
    """FAQ 直查 — MVP 阶段返回节点标签和占位答案,后续 SPEC-F1 上线后接 KB。

    Args:
        text: 用户问题
        node: 已知节点(可选),如不传则自动识别
    """
    matched_node = node or _find_faq_node(text)
    if not matched_node:
        return ChargeFaqHit(matched=False)

    # MVP: 返回节点 + 占位文字,等 FAQ KB 上线后从 KB 真实检索
    return ChargeFaqHit(
        matched=True,
        node=matched_node,
        question=text[:200],
        answer=(
            f"(本地兜底) 命中 FAQ 节点: {matched_node}。"
            f"知识库 FAQ 上线后,此处将返回 `常见问题解答.xlsx` 中的真实答案。"
        ),
        answer_hash=None,
        related_manual_chapter=matched_node,  # FAQ 21 节点与手册 35 标题有 19 重叠
    )


# ── 兜底 SceneResponse 构造 ──────────────────────────────────
def build_local_fallback(
    text: str,
    language: str = "zh",
    hint_endpoint: Optional[str] = None,
    hint_region: Optional[str] = None,
) -> ChargeSceneResponse:
    """本地兜底: 综合 4 维分类 + 危险信号 + FAQ,生成完整 ChargeSceneResponse。"""
    from datetime import datetime, timezone

    scene, endpoint, region, pile_type, confidence = classify_4d(
        text, language, hint_endpoint, hint_region
    )
    danger = match_danger_signals(text, endpoint=endpoint)
    faq = lookup_faq(text)

    # 风险等级 — 危险信号优先
    risk_level: ChargeRiskLevel = "low"
    if danger.matched:
        risk_level = danger.risk_level
    elif scene == "after_sales":
        risk_level = "medium"
    elif scene == "fallback":
        risk_level = "low"

    # 主回复文字
    if danger.matched and danger.fallback_message:
        text_reply = danger.fallback_message
    elif faq.matched and faq.answer:
        text_reply = faq.answer
    elif scene == "pricing":
        text_reply = "(本地兜底) 报价场景已识别,流程3 报价查询结果将通过 Dify 返回"
    elif scene == "after_sales":
        text_reply = "(本地兜底) 已识别为售后问题,流程1+流程2 预检完成后将返回诊断"
    elif scene == "pre_sale":
        text_reply = "(本地兜底) 已识别为售前咨询,功能匹配预检后将返回功能清单"
    else:
        text_reply = (
            "(本地兜底) 暂未识别到具体意图,请补充描述: "
            "您是想问功能 / 故障 / 操作 / 报价 哪一类?"
        )

    # Next actions
    next_actions: list[NextAction] = []
    if danger.matched:
        next_actions.append(
            NextAction(
                type="call_support",
                label="联系售后",
                payload={"phone": "400-xxx-xxxx"},
            )
        )
    if scene == "pricing" or faq.matched:
        next_actions.append(
            NextAction(type="show_steps", label="查看详情", payload={})
        )

    # 构造 payload
    from charge_consult.schemas import ChargePayload

    payload = ChargePayload(
        text=text_reply,
        flow1_matched=None,
        flow2_verified=None,
        flow3_pricing=None,
        faq=faq,
        danger=danger,
        manual={},
        pricing_table=[],
        next_actions=next_actions,
    )

    return ChargeSceneResponse(
        scene=scene,
        endpoint=endpoint,
        region=region,
        pile_type=pile_type,
        risk_level=risk_level,
        confidence=confidence,
        payload=payload,
        raw=None,
        source="local_fallback",
        ts=datetime.now(timezone.utc).isoformat(),
    )
