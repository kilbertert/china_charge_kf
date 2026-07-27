"""The runtime charge facts must stay reproducible from tracked source files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_generated_charge_facts_are_current() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_charge_service_facts.py"), "--check"],
        cwd=ROOT,
        check=True,
    )


def test_generated_facts_keep_verified_business_boundaries() -> None:
    data = yaml.safe_load(
        (ROOT / "shared" / "charge_service.yaml").read_text(encoding="utf-8")
    )
    billing = data["verified_knowledge"]["billing_templates"]
    fault = data["verified_knowledge"]["user_fault_repair"]
    order = data["verified_knowledge"]["order_management"]

    assert billing["standard_pc_path"] == ["充电桩", "计费管理", "充电计费模板"]
    assert "需关联对应站点方可生效" in billing["activation_rule"]
    assert "不是创建或关联计费模板的前置条件" in billing["guardrails"]["minimum_start_amount"]
    assert fault["custom_link"] == "/charge/pages/malfunction/malfunction"
    assert "具体项目" in fault["availability"]
    assert order["pc_path"] == ["财务", "订单中心", "充电桩订单", "新能源车充电订单"]
    assert "导出" in order["filter_rule"]
