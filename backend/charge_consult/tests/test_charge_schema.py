"""ChargeSceneResponse 4 维分类 schema 验证 — SPEC-A1 测试。

覆盖:
  - 4 维枚举值合法性
  - 必填字段
  - FAQ 路径(命中 21 个节点)
  - 危险信号硬闸门路径(SPEC-D2 兜底)
  - Fallback 路径
  - Confidence 区间
  - Payload 嵌套结构
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from charge_consult.schemas import (
    CHARGE_ENDPOINT_ENUMS,
    CHARGE_PILE_TYPE_ENUMS,
    CHARGE_REGION_ENUMS,
    CHARGE_RISK_ENUMS,
    CHARGE_SCENE_ENUMS,
    ChargeChatRequest,
    ChargeDangerSignalHit,
    ChargeEndpoint,
    ChargeFaqHit,
    ChargePayload,
    ChargePileType,
    ChargeRegion,
    ChargeRiskLevel,
    ChargeScene,
    ChargeSceneResponse,
    NextAction,
)
from charge_consult.scene_router import (
    build_local_fallback,
    classify_4d,
    lookup_faq,
    match_danger_signals,
)


# ── Fixtures ──────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_payload(text: str = "test") -> ChargePayload:
    return ChargePayload(text=text)


# ── 枚举值测试 ────────────────────────────────────────────────
class TestEnums:
    def test_scene_enums_6个(self):
        assert len(CHARGE_SCENE_ENUMS) == 6
        assert set(CHARGE_SCENE_ENUMS) == {
            "pre_sale", "after_sales", "operation", "pricing", "faq", "fallback",
        }

    def test_endpoint_enums_3个(self):
        assert len(CHARGE_ENDPOINT_ENUMS) == 3
        assert set(CHARGE_ENDPOINT_ENUMS) == {"user", "butler", "pc"}

    def test_region_enums_2个(self):
        assert len(CHARGE_REGION_ENUMS) == 2
        assert set(CHARGE_REGION_ENUMS) == {"cn", "overseas"}

    def test_pile_type_enums_2个(self):
        assert len(CHARGE_PILE_TYPE_ENUMS) == 2
        assert set(CHARGE_PILE_TYPE_ENUMS) == {"public", "home"}

    def test_risk_enums_4个(self):
        assert len(CHARGE_RISK_ENUMS) == 4
        assert set(CHARGE_RISK_ENUMS) == {"low", "medium", "high", "urgent"}


# ── ChargeSceneResponse 基础校验 ──────────────────────────────
class TestChargeSceneResponse:
    def test_必填字段缺失ts会报错(self):
        with pytest.raises(Exception):
            ChargeSceneResponse(scene="pre_sale", payload=_make_payload())

    def test_confidence_超出0_1范围会报错(self):
        with pytest.raises(Exception):
            ChargeSceneResponse(
                scene="pre_sale",
                payload=_make_payload(),
                ts=_now_iso(),
                confidence=1.5,  # 越界
            )
        with pytest.raises(Exception):
            ChargeSceneResponse(
                scene="pre_sale",
                payload=_make_payload(),
                ts=_now_iso(),
                confidence=-0.1,  # 越界
            )

    def test_confidence_0和1是合法的(self):
        ChargeSceneResponse(
            scene="pre_sale",
            payload=_make_payload(),
            ts=_now_iso(),
            confidence=0.0,
        )
        ChargeSceneResponse(
            scene="pre_sale",
            payload=_make_payload(),
            ts=_now_iso(),
            confidence=1.0,
        )

    def test_4维字段都有默认值(self):
        r = ChargeSceneResponse(
            scene="pre_sale",
            payload=_make_payload(),
            ts=_now_iso(),
        )
        assert r.endpoint == "user"
        assert r.region == "cn"
        assert r.pile_type == "public"
        assert r.risk_level == "low"
        assert r.confidence == 1.0
        assert r.source == "dify"

    def test_json序列化可逆(self):
        r = ChargeSceneResponse(
            scene="after_sales",
            endpoint="user",
            region="cn",
            pile_type="home",
            risk_level="urgent",
            confidence=0.95,
            payload=_make_payload("立即停止"),
            source="local_fallback",
            ts=_now_iso(),
        )
        json_str = r.model_dump_json()
        # JSON 可解析
        parsed = json.loads(json_str)
        assert parsed["scene"] == "after_sales"
        assert parsed["risk_level"] == "urgent"
        assert parsed["pile_type"] == "home"


# ── 4 维分类本地兜底路径 ──────────────────────────────────────
class TestClassify4D:
    def test_售前场景(self):
        scene, ep, reg, pt, conf = classify_4d("这桩有什么功能?")
        assert scene == "pre_sale"
        assert conf >= 0.9

    def test_报价场景(self):
        scene, _, _, _, _ = classify_4d("7kW 充电桩多少钱?")
        assert scene == "pricing"

    def test_售后危险信号(self):
        scene, _, _, _, _ = classify_4d("我的桩漏电了")
        assert scene == "after_sales"

    def test_FAQ英文节点(self):
        scene, _, _, _, conf = classify_4d("How to set Role Management?")
        assert scene == "faq"
        assert conf == 1.0

    def test_FAQ中文节点(self):
        scene, _, _, _, conf = classify_4d("怎么进行角色管理?")
        assert scene == "faq"
        assert conf == 1.0

    def test_空文本走fallback(self):
        scene, ep, reg, pt, conf = classify_4d("")
        assert scene == "fallback"
        assert conf == 0.3

    def test_endpoint_pc_hints(self):
        _, ep, _, _, _ = classify_4d("角色管理权限分配")
        assert ep == "pc"

    def test_endpoint_butler_hints(self):
        _, ep, _, _, _ = classify_4d("运营商分润比例怎么算?")
        assert ep == "butler"

    def test_endpoint_默认user(self):
        _, ep, _, _, _ = classify_4d("我的桩有什么功能?")
        assert ep == "user"

    def test_region_overseas_通过language(self):
        _, _, reg, _, _ = classify_4d("any question", language="en")
        assert reg == "overseas"

    def test_region_overseas_通过关键词(self):
        _, _, reg, _, _ = classify_4d("如何使用谷歌登录?")
        assert reg == "overseas"

    def test_pile_type_home(self):
        _, _, _, pt, _ = classify_4d("我想了解家充桩")
        assert pt == "home"

    def test_pile_type_home_英文(self):
        _, _, _, pt, _ = classify_4d("I need a home charger")
        assert pt == "home"

    def test_hint_endpoint_覆盖启发式(self):
        _, ep, _, _, _ = classify_4d("随便问", hint_endpoint="pc")
        assert ep == "pc"

    def test_hint_region_覆盖启发式(self):
        _, _, reg, _, _ = classify_4d("随便问", hint_region="overseas")
        assert reg == "overseas"


# ── 危险信号硬闸门路径(SPEC-D2 兜底) ─────────────────────────
class TestDangerSignals:
    def test_用户端漏电(self):
        hit = match_danger_signals("我的桩漏电了", endpoint="user")
        assert hit.matched is True
        assert hit.keyword == "漏电"
        assert hit.risk_level == "urgent"
        assert "立即" in (hit.action or "")

    def test_管家端分润异常(self):
        hit = match_danger_signals("分润异常", endpoint="butler")
        assert hit.matched is True
        assert hit.endpoint == "butler"

    def test_PC端设备故障(self):
        hit = match_danger_signals("Equipment Failure 多", endpoint="pc")
        assert hit.matched is True
        assert hit.endpoint == "pc"

    def test_不命中返回默认(self):
        hit = match_danger_signals("我的桩怎么用?")
        assert hit.matched is False
        assert hit.keyword is None

    def test_管家端_不查用户端词(self):
        """端隔离: 管家端不应该命中 '漏电'(那是用户端词)。"""
        hit = match_danger_signals("我的桩漏电了", endpoint="butler")
        assert hit.matched is False

    def test_空文本返回默认(self):
        hit = match_danger_signals("")
        assert hit.matched is False


# ── FAQ 直查路径(SPEC-B1 5002-2) ─────────────────────────────
class TestFaqLookup:
    def test_命中英文节点(self):
        hit = lookup_faq("How to handle Site audit?")
        assert hit.matched is True
        assert hit.node == "Site audit"

    def test_命中中文节点(self):
        hit = lookup_faq("请问计费模板怎么配置?")
        assert hit.matched is True
        assert hit.node == "Billing Template"

    def test_不命中返回matched_false(self):
        hit = lookup_faq("今天天气怎么样?")
        assert hit.matched is False

    def test_显式传node(self):
        hit = lookup_faq("任意文本", node="Equipment Failure List")
        assert hit.matched is True
        assert hit.node == "Equipment Failure List"

    def test_关联到手册章节(self):
        hit = lookup_faq("Role Management 怎么用?")
        assert hit.matched is True
        assert hit.related_manual_chapter == "Role Management"


# ── 兜底 SceneResponse 完整构造 ──────────────────────────────
class TestBuildLocalFallback:
    def test_售前兜底(self):
        r = build_local_fallback("这桩有什么功能?")
        assert r.scene == "pre_sale"
        assert r.endpoint == "user"
        assert r.region == "cn"
        assert r.pile_type == "public"
        assert r.source == "local_fallback"
        assert r.confidence >= 0.9
        assert "本地兜底" in r.payload.text

    def test_危险信号兜底_升级risk(self):
        r = build_local_fallback("我的桩漏电了,跳闸后无法复位")
        assert r.scene == "after_sales"
        assert r.risk_level == "urgent"
        assert r.payload.danger.matched is True
        # 兜底文字以危险信号为主
        assert "⚠️" in r.payload.text or "漏电" in r.payload.text or "立即" in r.payload.text
        # next_actions 含 call_support
        types = [a.type for a in r.payload.next_actions]
        assert "call_support" in types

    def test_FAQ兜底(self):
        r = build_local_fallback("Role Management 是什么?")
        assert r.scene == "faq"
        assert r.payload.faq.matched is True
        assert r.payload.faq.node == "Role Management"

    def test_家充场景识别(self):
        r = build_local_fallback("我家的家用充电桩怎么用?")
        assert r.pile_type == "home"

    def test_海外语言识别(self):
        r = build_local_fallback("any question", language="en")
        assert r.region == "overseas"

    def test_空文本走fallback(self):
        r = build_local_fallback("")
        assert r.scene == "fallback"
        assert r.confidence == 0.3

    def test_时间戳ISO8601格式(self):
        r = build_local_fallback("测试")
        # 必须能被 datetime 解析
        datetime.fromisoformat(r.ts)


# ── ChargeChatRequest 表单验证 ────────────────────────────────
class TestChargeChatRequest:
    def test_默认参数(self):
        req = ChargeChatRequest()
        assert req.text == ""
        assert req.turn == 1
        assert req.language == "zh"

    def test_turn范围1到20(self):
        with pytest.raises(Exception):
            ChargeChatRequest(turn=0)
        with pytest.raises(Exception):
            ChargeChatRequest(turn=21)

    def test_language只能zh_en_vi(self):
        with pytest.raises(Exception):
            ChargeChatRequest(language="jp")  # type: ignore[arg-type]

    def test_text超过4000会报错(self):
        with pytest.raises(Exception):
            ChargeChatRequest(text="a" * 4001)


# ── 集成: 端到端验证工作流 4 维输出 ─────────────────────────
class TestEndToEnd4D:
    @pytest.mark.parametrize("text,expected_scene,expected_endpoint,expected_pile_type", [
        ("这桩有什么功能?", "pre_sale", "user", "public"),
        ("7kW 充电桩多少钱?", "pricing", "user", "public"),
        ("我的桩漏电了", "after_sales", "user", "public"),
        ("Role Management 权限怎么分配?", "faq", "pc", "public"),
        ("家充桩怎么申请?", "fallback", "user", "home"),  # "申请" 不在售前/售后词里,留待后续优化
        ("运营商分润异常", "after_sales", "butler", "public"),  # 危险信号优先于 FAQ
        ("Equipment Failure", "after_sales", "pc", "public"),   # 危险信号优先于 FAQ
    ])
    def test_典型场景(self, text, expected_scene, expected_endpoint, expected_pile_type):
        r = build_local_fallback(text)
        assert r.scene == expected_scene
        assert r.endpoint == expected_endpoint
        assert r.pile_type == expected_pile_type
