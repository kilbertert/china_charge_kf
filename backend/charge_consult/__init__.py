"""charge_consult — 充电桩客服咨询模块。

对应 Dify workflow: `China_charge_seriver`(node ID 5001-5099)
对应前端路由: `?view=charge` (后续追加)
对应数据源: `Workflow-China_charge_seriver-draft-9380/knowledge_bases/*`

本模块负责:
  1. 定义 4 维分类契约 (scene + endpoint + region + pile_type)
  2. 本地兜底 scene_router(Dify 不可用时降级)
  3. 危险信号关键词后端维护(后续从 CMS / DB 拉取,MVP 写死)
  4. 与 frontend H5 端对齐(供 useSceneChat 消费)
"""

from charge_consult.schemas import (
    CHARGE_SCENE_ENUMS,
    CHARGE_ENDPOINT_ENUMS,
    CHARGE_REGION_ENUMS,
    CHARGE_PILE_TYPE_ENUMS,
    CHARGE_RISK_ENUMS,
    ChargeChatRequest,
    ChargeDangerSignal,
    ChargeDangerSignalHit,
    ChargeFaqHit,
    ChargePayload,
    ChargeSceneResponse,
    DangerSignalsConfig,
    NextAction,
)

__all__ = [
    "CHARGE_SCENE_ENUMS",
    "CHARGE_ENDPOINT_ENUMS",
    "CHARGE_REGION_ENUMS",
    "CHARGE_PILE_TYPE_ENUMS",
    "CHARGE_RISK_ENUMS",
    "ChargeChatRequest",
    "ChargeDangerSignal",
    "ChargeDangerSignalHit",
    "ChargeFaqHit",
    "ChargePayload",
    "ChargeSceneResponse",
    "DangerSignalsConfig",
    "NextAction",
]
