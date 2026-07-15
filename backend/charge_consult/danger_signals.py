"""危险信号配置 — SPEC-D2 5020 节点依赖。

维护原则(已与用户对齐):
  - 关键词维护放后端,Dify 通过 HTTP 节点动态拉取
  - 端类型分组: 用户端 / 管家端 / PC 后台 各一组
  - MVP 写死,后续接 CMS / DB(SPEC-G1 拓展)

格式: list[ChargeDangerSignal]
  - keyword:  匹配关键词(支持中文 + 英文,大小写不敏感)
  - endpoint: 该关键词在哪一端命中
  - risk_level: 命中后风险等级,通常 urgent
  - action: 建议动作文字

⚠️ 注意: 本文件需要周期性 review,任何漏电/安全相关关键词缺失都可能造成
   法律/合规风险,务必走 PR review 流程。
"""

from __future__ import annotations

from charge_consult.schemas import (
    ChargeDangerSignal,
    DangerSignalsConfig,
)


# ── 用户端(C 端) — 物理设备相关 ──────────────────────────────
_USER_DANGER_SIGNALS: list[ChargeDangerSignal] = [
    ChargeDangerSignal(
        keyword="漏电",
        endpoint="user",
        risk_level="urgent",
        action="立即停止充电,断开充电枪,联系专业电工 / 售后",
    ),
    ChargeDangerSignal(
        keyword="触电",
        endpoint="user",
        risk_level="urgent",
        action="立即远离设备,拨打 120 / 联系售后",
    ),
    ChargeDangerSignal(
        keyword="冒烟",
        endpoint="user",
        risk_level="urgent",
        action="立即停止充电,断开电源,远离设备,拨打 119",
    ),
    ChargeDangerSignal(
        keyword="起火",
        endpoint="user",
        risk_level="urgent",
        action="立即切断电源(如安全),使用干粉灭火器,拨打 119",
    ),
    ChargeDangerSignal(
        keyword="火花",
        endpoint="user",
        risk_level="high",
        action="立即停止充电,断开充电枪,联系售后",
    ),
    ChargeDangerSignal(
        keyword="烧焦",
        endpoint="user",
        risk_level="urgent",
        action="立即停止充电,断开电源,远离设备,联系售后",
    ),
    ChargeDangerSignal(
        keyword="异味",
        endpoint="user",
        risk_level="high",
        action="立即停止充电,断开电源,远离设备,联系售后",
    ),
    ChargeDangerSignal(
        keyword="跳闸",
        endpoint="user",
        risk_level="high",
        action="先断总闸,联系专业电工检查;如无法复位请勿继续使用",
    ),
    ChargeDangerSignal(
        keyword="充电中断",
        endpoint="user",
        risk_level="medium",
        action="先检查充电枪是否脱落,App 是否有提示码,再联系售后",
    ),
    ChargeDangerSignal(
        keyword="充不上电",
        endpoint="user",
        risk_level="medium",
        action="检查余额 / 设备状态 / 充电枪连接,问题持续请联系售后",
    ),
    ChargeDangerSignal(
        keyword="余额不足",
        endpoint="user",
        risk_level="low",
        action="前往 App 充值后重试",
    ),
]


# ── 管家端(B 端) — 运营/分润相关 ──────────────────────────────
_BUTLER_DANGER_SIGNALS: list[ChargeDangerSignal] = [
    ChargeDangerSignal(
        keyword="分润异常",
        endpoint="butler",
        risk_level="high",
        action="核对分润比例配置,如平台上限异常请联系运营",
    ),
    ChargeDangerSignal(
        keyword="结算延迟",
        endpoint="butler",
        risk_level="high",
        action="核对结算周期配置,联系平台运营核查账单",
    ),
    ChargeDangerSignal(
        keyword="设备离线",
        endpoint="butler",
        risk_level="medium",
        action="先排查网络/电源,如长时间离线请联系平台技术支持",
    ),
    ChargeDangerSignal(
        keyword="审核驳回",
        endpoint="butler",
        risk_level="low",
        action="修改后重新提交,常见驳回原因见运营规范",
    ),
    ChargeDangerSignal(
        keyword="押金",
        endpoint="butler",
        risk_level="low",
        action="押金为记录配置项,无需线上支付,联系平台人员线下缴纳",
    ),
]


# ── PC 后台(平台) — 财务 / 设备总览 ───────────────────────────
_PC_DANGER_SIGNALS: list[ChargeDangerSignal] = [
    ChargeDangerSignal(
        keyword="Abnormal Charging Monitoring",
        endpoint="pc",
        risk_level="high",
        action="在「订单管理 → 异常订单」中查看告警详情,联系运营核查",
    ),
    ChargeDangerSignal(
        keyword="Equipment Failure",
        endpoint="pc",
        risk_level="high",
        action="在「设备故障列表」中确认故障码,联系运营商现场处理",
    ),
    ChargeDangerSignal(
        keyword="退款待处理",
        endpoint="pc",
        risk_level="medium",
        action="在「退款审核」中按时间排序处理,优先 24h 内申请",
    ),
    ChargeDangerSignal(
        keyword="充值审核",
        endpoint="pc",
        risk_level="low",
        action="需财务/运营权限,核对金额 + 凭证后通过",
    ),
]


# ── 合并所有端的危险信号(按 endpoint 索引) ─────────────────────
DANGER_SIGNALS_BY_ENDPOINT: dict[str, list[ChargeDangerSignal]] = {
    "user": _USER_DANGER_SIGNALS,
    "butler": _BUTLER_DANGER_SIGNALS,
    "pc": _PC_DANGER_SIGNALS,
}

# 全局索引(给"未指定端"场景用,默认只查 user 端)
ALL_DANGER_SIGNALS: list[ChargeDangerSignal] = (
    _USER_DANGER_SIGNALS + _BUTLER_DANGER_SIGNALS + _PC_DANGER_SIGNALS
)


# ── 当前生效的配置对象 ─────────────────────────────────────────
# MVP 写死;后续 SPEC-G1 阶段会从 CMS / DB 动态加载
DANGER_SIGNALS_CONFIG = DangerSignalsConfig(
    signals=ALL_DANGER_SIGNALS,
    last_updated="2026-06-18T00:00:00Z",
    version="0.1.0-mvp",
)


def get_danger_signals(endpoint: str | None = None) -> list[ChargeDangerSignal]:
    """按端类型获取危险信号列表。

    Args:
        endpoint: "user" | "butler" | "pc" | None(返回全部)

    Returns:
        该端类型下的全部危险信号。
    """
    if endpoint and endpoint in DANGER_SIGNALS_BY_ENDPOINT:
        return DANGER_SIGNALS_BY_ENDPOINT[endpoint]
    return ALL_DANGER_SIGNALS
