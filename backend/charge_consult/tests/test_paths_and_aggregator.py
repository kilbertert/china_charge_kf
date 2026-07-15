"""路径处理器 + End 聚合 测试 — SPEC-D1/D3/D/B1/E1。"""

from __future__ import annotations

import json

import pytest

from charge_consult.end_aggregator import (
    aggregate_from_dify_inputs,
    aggregate_scene_response,
    from_dify_raw_output,
    to_end_node_output,
    validate_end_output,
)
from charge_consult.path_handlers import (
    build_path_a_payload,
    build_path_b_urgent_payload,
    build_path_c_payload,
    build_path_d_payload,
    build_path_e_payload,
    extract_deep_links,
)
from charge_consult.schemas import ChargePayload, ChargeSceneResponse


# ── 路径 A: 售前 ──────────────────────────────────────────
class TestPathA:
    def test_命中定时充电(self):
        hits = [{"name": "定时充电", "version_added": "V2.1", "description": "..."}]
        p = build_path_a_payload("定时充电怎么用?", hits, [])
        assert p.flow1_matched is True
        assert p.matched_function == "定时充电"
        assert p.matched_version == "V2.1"
        assert "1. 打开 App" in p.text
        assert any(a.type == "show_steps" for a in p.next_actions)

    def test_未命中但有flow1结果(self):
        hits = [{"name": "扫码充电", "version_added": "V2.0", "description": "扫描设备二维码启动充电"}]
        p = build_path_a_payload("其他问题", hits, [])
        assert p.flow1_matched is True
        assert p.matched_function is None
        assert "扫码充电" in p.text

    def test_完全无命中(self):
        p = build_path_a_payload("随机问题", [], [])
        assert p.flow1_matched is False
        assert "未找到匹配" in p.text

    def test_空flow1_top_k(self):
        p = build_path_a_payload("问题", [], [])
        assert p.flow1_matched is False


# ── 路径 C: 操作指导 ──────────────────────────────────────
class TestPathC:
    def test_手册片段有步骤(self):
        manual = [{
            "chapter": "Fault Repair",
            "steps": ["打开 App", "点击报修", "填写故障描述"],
            "deep_link": "/charge/pages/malfunction/malfunction",
            "language": "zh",
        }]
        p = build_path_c_payload("怎么报修?", manual)
        assert p.manual["chapter"] == "Fault Repair"
        assert len(p.manual["steps"]) == 3
        assert "1. 打开 App" in p.text
        assert "/charge/pages/malfunction/malfunction" in p.text
        assert p.next_actions[0].type == "open_url"

    def test_无手册片段走兜底(self):
        p = build_path_c_payload("?", [])
        assert "未找到匹配" in p.text
        assert p.manual == {}

    def test_字符串步骤自动转list(self):
        manual = [{"chapter": "X", "steps": "单步操作"}]
        p = build_path_c_payload("?", manual)
        assert p.manual["steps"] == ["单步操作"]

    def test_extract_deep_links_保留所有链接(self):
        text = "点击 /charge/pages/malfunction/malfunction 跳转,也可访问 /admin/system/role"
        links = extract_deep_links(text)
        assert "/charge/pages/malfunction/malfunction" in links
        assert "/admin/system/role" in links
        assert len(links) == 2

    def test_extract_deep_links_去重保序(self):
        text = "/charge/pages/a /charge/pages/a /charge/pages/b"
        links = extract_deep_links(text)
        assert links == ["/charge/pages/a", "/charge/pages/b"]


# ── 路径 D: 报价 ──────────────────────────────────────────
class TestPathD:
    def test_有报价行(self):
        hits = [{
            "sku": "CHARGER-7KW-CN",
            "product_name_zh": "7kW 家用充电桩",
            "price": "2580.00",
            "currency": "CNY",
            "valid_until": "2026-12-31",
        }]
        p = build_path_d_payload("7kW 多少钱?", hits)
        assert p.flow3_pricing is not None
        assert "2580" in p.text
        assert "CNY" in p.text
        assert len(p.pricing_table) == 1

    def test_无报价行走兜底(self):
        p = build_path_d_payload("?", [])
        assert p.text == "暂无报价,请联系销售。"
        assert p.pricing_table == []

    def test_最多5行(self):
        hits = [{"sku": f"X-{i}", "price": "100", "currency": "CNY"} for i in range(10)]
        p = build_path_d_payload("?", hits)
        assert len(p.pricing_table) == 5


# ── 路径 E: 兜底引导 ──────────────────────────────────────
class TestPathE:
    def test_中文(self):
        p = build_path_e_payload("?", language="zh")
        assert "没太理解" in p.text
        assert "产品功能" in p.text
        assert len(p.next_actions) == 4

    def test_英文(self):
        p = build_path_e_payload("?", language="en")
        assert "didn't quite catch" in p.text

    def test_越南语(self):
        p = build_path_e_payload("?", language="vi")
        assert "chưa hiểu" in p.text


# ── 路径 B 紧急兜底 ──────────────────────────────────────
class TestPathBUrgent:
    def test_中文紧急(self):
        p = build_path_b_urgent_payload("漏电", "立即停止充电", "user", "zh")
        assert "⚠️" in p.text
        assert "漏电" in p.text
        assert "立即停止充电" in p.text
        assert p.next_actions[0].type == "call_support"

    def test_英文紧急(self):
        p = build_path_b_urgent_payload("leakage", "stop charging", "user", "en")
        assert "WARNING" in p.text
        assert "leakage" in p.text


# ── End 聚合 ──────────────────────────────────────────────
class TestEndAggregator:
    def test_aggregate_基础字段(self):
        r = aggregate_scene_response(
            scene="pre_sale",
            endpoint="user",
            region="cn",
            pile_type="public",
            risk_level="low",
            confidence=0.9,
            payload={"text": "你好"},
        )
        assert r.scene == "pre_sale"
        assert r.payload.text == "你好"
        assert r.confidence == 0.9
        assert r.source == "dify"

    def test_aggregate_未知_scene降级为_fallback(self):
        r = aggregate_scene_response(
            scene="unknown_scene",
            confidence=0.9,
            payload={"text": "test"},
        )
        assert r.scene == "fallback"
        assert r.confidence == 0.3

    def test_aggregate_payload接受_dict和_ChargePayload(self):
        r1 = aggregate_scene_response(scene="pre_sale", payload={"text": "x"})
        assert r1.payload.text == "x"
        r2 = aggregate_scene_response(scene="pre_sale", payload=ChargePayload(text="y"))
        assert r2.payload.text == "y"

    def test_aggregate_confidence_超界拒绝(self):
        with pytest.raises(Exception):
            aggregate_scene_response(scene="pre_sale", confidence=1.5, payload={"text": "x"})

    def test_aggregate_from_dify_inputs(self):
        inputs = {
            "scene": "after_sales",
            "endpoint": "user",
            "region": "cn",
            "pile_type": "public",
            "risk_level": "urgent",
            "confidence": 1.0,
            "payload": {
                "text": "漏电",
                "danger": {"matched": True, "keyword": "漏电", "risk_level": "urgent"},
            },
        }
        r = aggregate_from_dify_inputs(inputs)
        assert r.scene == "after_sales"
        assert r.risk_level == "urgent"
        assert r.payload.danger.matched is True
        assert r.payload.danger.keyword == "漏电"

    def test_to_end_node_output_合法JSON(self):
        r = aggregate_scene_response(scene="pre_sale", payload={"text": "x"})
        out = to_end_node_output(r)
        parsed = json.loads(out)
        assert parsed["scene"] == "pre_sale"
        assert parsed["payload"]["text"] == "x"

    def test_from_dify_raw_output_解析(self):
        s = '{"scene": "faq", "payload": {"text": "y"}}'
        parsed = from_dify_raw_output(s)
        assert parsed["scene"] == "faq"
        d = {"scene": "x"}
        assert from_dify_raw_output(d) is d
        bad = from_dify_raw_output("not json")
        assert "_parse_error" in bad

    def test_validate_end_output_合法(self):
        out = {
            "scene": "pre_sale",
            "endpoint": "user",
            "region": "cn",
            "pile_type": "public",
            "risk_level": "low",
            "payload": {"text": "ok"},
            "ts": "2026-06-18T00:00:00Z",
            "confidence": 1.0,
        }
        valid, errors = validate_end_output(out)
        assert valid, errors

    def test_validate_end_output_缺scene(self):
        out = {
            "endpoint": "user",
            "region": "cn",
            "pile_type": "public",
            "risk_level": "low",
            "payload": {"text": "ok"},
            "ts": "2026-06-18T",
        }
        valid, errors = validate_end_output(out)
        assert not valid
        assert any("scene" in e for e in errors)

    def test_validate_end_output_非法scene(self):
        out = {
            "scene": "garbage",
            "endpoint": "user",
            "region": "cn",
            "pile_type": "public",
            "risk_level": "low",
            "payload": {"text": "ok"},
            "ts": "2026-06-18T",
        }
        valid, errors = validate_end_output(out)
        assert not valid
        assert any("invalid scene" in e for e in errors)

    def test_validate_end_output_confidence越界(self):
        out = {
            "scene": "pre_sale",
            "endpoint": "user",
            "region": "cn",
            "pile_type": "public",
            "risk_level": "low",
            "payload": {"text": "ok"},
            "ts": "2026-06-18T",
            "confidence": 2.0,
        }
        valid, errors = validate_end_output(out)
        assert not valid
        assert any("confidence" in e for e in errors)


# ── 端到端: 4 路径都产出合规 ChargeSceneResponse ──────────
class TestEndToEndAllPaths:
    @pytest.mark.parametrize("scene,payload_obj", [
        ("pre_sale", build_path_a_payload("定时充电怎么用?", [{"name": "定时充电", "version_added": "V2.1"}], [])),
        ("operation", build_path_c_payload("怎么报修?", [{"chapter": "X", "steps": ["s1"], "deep_link": "/p"}])),
        ("pricing", build_path_d_payload("?", [{"sku": "X", "price": "100", "currency": "CNY"}])),
        ("fallback", build_path_e_payload("?", "zh")),
        ("after_sales", build_path_b_urgent_payload("漏电", "立即停止", "user", "zh")),
    ])
    def test_路径输出可被End聚合(self, scene, payload_obj):
        r = aggregate_scene_response(
            scene=scene,
            payload=payload_obj.model_dump(mode="json"),
            risk_level="urgent" if scene == "after_sales" else "low",
        )
        assert isinstance(r, ChargeSceneResponse)
        assert r.scene == scene
        assert r.ts
        assert r.payload.text is not None
