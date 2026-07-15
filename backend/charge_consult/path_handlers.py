"""路径处理器 — SPEC-D1 路径 A / SPEC-D3 路径 C / SPEC-D 路径 D / SPEC-B1 路径 E。

每个路径处理器都是纯函数,接收输入返回 ChargePayload 字段。
Dify yml 的 LLM 节点可以参考 prompt,后端兜底可以直接调用这些函数。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from charge_consult.schemas import (
    ChargeEndpoint,
    ChargePayload,
    ChargePileType,
    ChargeRegion,
    ChargeRiskLevel,
    ChargeScene,
    NextAction,
)


# ── 路径 A: 售前/功能咨询(SPEC-D1) ──────────────────────────
PATH_A_SYSTEM_PROMPT = """你是充电桩产品顾问。基于流程1(功能矩阵)和流程2(版本变更)的结果,回答用户的功能性问题。

约束:
1. 输出语言: 严格使用 {{input_language}}(中文/英文/越南语)
2. 价格/参数: 必须从 KB 原文复制,不允许编造
3. 格式: 使用编号列表,不要长段落
4. 命中功能点: 标注 matched_function 和 matched_version
5. 不确定: 明确说"该功能暂未实现/暂未在您所在区域上线"
"""

# 常见售前功能点 → 步骤化包装
PRESALE_FUNCTION_TEMPLATES = {
    "定时充电": [
        "1. 打开 App,点击'我的桩' → '充电设置'",
        "2. 选择'定时充电'功能",
        "3. 设置开始/结束时间(支持 7 天循环)",
        "4. 点击'保存',系统在指定时段自动开始/停止充电",
    ],
    "远程启动": [
        "1. App 首页 → '扫码' 或选择已绑定设备",
        "2. 点击'启动充电'按钮",
        "3. 确认订单信息,点击'确认启动'",
    ],
    "余额查询": [
        "1. App 首页 → '我的'",
        "2. 在'账户'模块查看余额",
        "3. 如需充值,点击'充值'选择金额和支付方式",
    ],
}


def build_path_a_payload(
    text: str,
    flow1_top_k: list,
    flow2_top_k: list,
    endpoint: ChargeEndpoint = "user",
    region: ChargeRegion = "cn",
    pile_type: ChargePileType = "public",
) -> ChargePayload:
    """路径 A 兜底: 根据 flow1/2 结果生成售前回答 payload。"""
    matched_function = None
    matched_version = None
    flow1_matched = bool(flow1_top_k)
    flow2_verified = bool(flow2_top_k)

    for hit in flow1_top_k:
        if isinstance(hit, dict):
            name = hit.get("name") or hit.get("function_name") or ""
            if name and name in text:
                matched_function = name
                matched_version = hit.get("version_added", "")
                break

    if matched_function and matched_function in PRESALE_FUNCTION_TEMPLATES:
        steps_text = "\n".join(PRESALE_FUNCTION_TEMPLATES[matched_function])
        text_reply = f"「{matched_function}」({matched_version or 'V2.4+'})操作步骤:\n\n{steps_text}"
    elif flow1_top_k:
        first_hit = flow1_top_k[0] if isinstance(flow1_top_k[0], dict) else {}
        name = first_hit.get("name", "")
        desc = first_hit.get("description", "")
        text_reply = f"「{name}」{desc[:200]}\n\n(详细操作步骤请见操作手册)"
    else:
        text_reply = "未找到匹配的功能,已记录您的提问。如需了解具体功能(如定时充电、远程启动),请提供更具体的问题。"

    next_actions = [NextAction(type="show_steps", label="查看详情", payload={})]

    return ChargePayload(
        text=text_reply,
        flow1_matched=flow1_matched,
        flow2_verified=flow2_verified,
        flow3_pricing=None,
        next_actions=next_actions,
        matched_function=matched_function,
        matched_version=matched_version,
    )


# ── 路径 C: 操作指导(SPEC-D3) ───────────────────────────────
PATH_C_SYSTEM_PROMPT = """你是充电桩平台操作指南助手。根据操作手册(PC管理后台/用户端/管家端)片段,回答用户的操作问题。

约束:
1. 输出语言: 严格使用 {{input_language}}(zh/en/vi)
2. 格式: 编号步骤,每步独立一行
3. 链接保留: 手册中的 /charge/pages/... 路径原样保留
4. 端过滤: 只回答 endpoint 对应端的内容
5. 多语言: 严格按 input_language 选 language metadata
"""

# 链接提取正则(SPEC-D3 5032 节点必须保留)
DEEP_LINK_RE = re.compile(r"(/charge/pages/[a-zA-Z0-9/_-]+|/admin/[a-zA-Z0-9/_-]+)")


def extract_deep_links(text: str) -> list:
    """从手册片段中提取 deep_link 路径,去重保序。"""
    if not text:
        return []
    return list(dict.fromkeys(DEEP_LINK_RE.findall(text)))


def build_path_c_payload(
    text: str,
    manual_top_k: list,
    endpoint: ChargeEndpoint = "user",
    language: str = "zh",
) -> ChargePayload:
    """路径 C 兜底: 提取手册步骤 + 保留 deep_link。"""
    if not manual_top_k:
        return ChargePayload(
            text=f"未找到匹配的操作手册片段。如需操作 '{endpoint}' 端的某个功能,请提供具体功能名。",
            manual={},
            next_actions=[NextAction(type="show_steps", label="查看帮助", payload={})],
        )

    top_hit = manual_top_k[0]
    chapter = top_hit.get("chapter", "")
    steps = top_hit.get("steps") or top_hit.get("step_text_zh") or top_hit.get("step_text_en") or ""
    if isinstance(steps, str):
        steps = [steps]
    deep_link = top_hit.get("deep_link", "")

    step_lines = [f"{i}. {s}" for i, s in enumerate(steps[:10], 1)]
    text_reply = f"「{chapter}」操作步骤:\n\n" + "\n".join(step_lines)
    if deep_link:
        text_reply += f"\n\n跳转链接: {deep_link}"

    all_links = extract_deep_links(text_reply)

    return ChargePayload(
        text=text_reply,
        manual={
            "chapter": chapter,
            "steps": steps[:10],
            "deep_link": deep_link,
            "language": language,
            "all_links": all_links,
            "endpoint": endpoint,
        },
        next_actions=[
            NextAction(
                type="open_url",
                label="打开页面" if deep_link else "查看详情",
                payload={"url": deep_link} if deep_link else {},
            ),
        ],
    )


# ── 路径 D: 报价(SPEC-C3 5040) ──────────────────────────────
PATH_D_SYSTEM_PROMPT = """你是充电桩产品报价助手。根据流程3 报价库检索结果,提供价格信息。

约束:
1. 输出语言: 严格使用 {{input_language}}
2. 价格: 必须从 KB 原文复制,不允许编造
3. 货币: 必须与 region 匹配(CN→CNY, NA→USD, EU→EUR, SEA→VND)
4. 过期: 标注"已过期"
5. 不允许"促销推荐"等模糊话术
6. 无匹配: 返回"暂无报价,请联系销售"
"""


def build_path_d_payload(
    text: str,
    flow3_top_k: list,
    region: ChargeRegion = "cn",
) -> ChargePayload:
    """路径 D 兜底: 从报价库抽取结构化数据。"""
    if not flow3_top_k:
        return ChargePayload(
            text="暂无报价,请联系销售。",
            pricing_table=[],
            next_actions=[NextAction(type="call_support", label="联系销售", payload={})],
        )

    pricing_table = []
    for hit in flow3_top_k[:5]:
        if isinstance(hit, dict):
            pricing_table.append({
                "sku": hit.get("sku", ""),
                "product_name_zh": hit.get("product_name_zh", ""),
                "product_name_en": hit.get("product_name_en", ""),
                "price": hit.get("price", ""),
                "currency": hit.get("currency", ""),
                "valid_until": hit.get("valid_until", ""),
            })

    if pricing_table:
        first = pricing_table[0]
        text_reply = (
            f"「{first.get('product_name_zh', first.get('product_name_en', '产品'))}」\n"
            f"价格: {first.get('price', '')} {first.get('currency', '')}\n"
            f"有效期至: {first.get('valid_until', '长期')}\n\n"
            f"完整列表见下方。"
        )
    else:
        text_reply = "未找到匹配报价。"

    return ChargePayload(
        text=text_reply,
        flow3_pricing=text_reply,
        pricing_table=pricing_table,
        next_actions=[NextAction(type="show_steps", label="查看完整报价", payload={})],
    )


# ── 路径 E: 兜底(SPEC-B1 5090) ──────────────────────────────
PATH_E_SYSTEM_PROMPT = """你是充电桩智能客服。用户的问题不够明确,需要你礼貌地引导用户补充信息。

约束:
1. 输出语言: 严格使用 {{input_language}}
2. 友好地引导用户描述具体场景
3. 提供 4 类问题的入口: 功能咨询 / 故障报修 / 操作指导 / 报价查询
"""


def build_path_e_payload(text: str, language: str = "zh") -> ChargePayload:
    """路径 E 兜底: 引导用户补充信息。"""
    if language == "en":
        text_reply = (
            "I didn't quite catch your question. Could you clarify what you need help with?\n\n"
            "1. **Product features** — e.g. Does this charger support scheduled charging?\n"
            "2. **Troubleshooting** — e.g. My charger shows a red light\n"
            "3. **Operations** — e.g. How to bind a vehicle in the app?\n"
            "4. **Pricing** — e.g. How much does the 7kW home charger cost?"
        )
    elif language == "vi":
        text_reply = (
            "Tôi chưa hiểu rõ câu hỏi của bạn. Bạn có thể mô tả cụ thể hơn không?\n\n"
            "1. Tính năng sản phẩm\n"
            "2. Sự cố\n"
            "3. Hướng dẫn thao tác\n"
            "4. Báo giá"
        )
    else:
        text_reply = (
            "您好,没太理解您的问题。您想咨询以下哪类?\n\n"
            "1. 产品功能 — 例: 这桩支持定时充电吗?\n"
            "2. 故障报修 — 例: 我的桩显示红灯\n"
            "3. 操作指导 — 例: App 怎么绑定车辆?\n"
            "4. 报价查询 — 例: 7kW 家充桩多少钱?"
        )

    return ChargePayload(
        text=text_reply,
        next_actions=[
            NextAction(type="show_steps", label="产品功能", payload={"scene": "pre_sale"}),
            NextAction(type="show_steps", label="故障报修", payload={"scene": "after_sales"}),
            NextAction(type="show_steps", label="操作指导", payload={"scene": "operation"}),
            NextAction(type="show_steps", label="报价查询", payload={"scene": "pricing"}),
        ],
    )


# ── 路径 B 紧急兜底(SPEC-D2 5022) ──────────────────────────
def build_path_b_urgent_payload(
    keyword: str,
    action: str,
    endpoint: ChargeEndpoint = "user",
    language: str = "zh",
) -> ChargePayload:
    """路径 B 紧急路径兜底: 危险信号命中,直接返回安全提示。"""
    if language == "en":
        text_reply = (
            f"WARNING: Dangerous signal detected: {keyword}.\n\n"
            f"Recommended action: {action}.\n\n"
            "Please take immediate action and contact support if needed."
        )
    elif language == "vi":
        text_reply = (
            f"CẢNH BÁO: Phát hiện tín hiệu nguy hiểm: {keyword}.\n\n"
            f"Hành động khuyến nghị: {action}."
        )
    else:
        text_reply = f"⚠️ 检测到危险信号: {keyword}。\n\n建议: {action}。\n\n请立即采取行动,如有需要请联系售后。"

    return ChargePayload(
        text=text_reply,
        # danger 字段省略,使用默认 factory
        next_actions=[
            NextAction(type="call_support", label="联系售后", payload={"phone": "400-xxx-xxxx"}),
        ],
    )
