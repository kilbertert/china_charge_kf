"""Patch AI_health_consultant_v2.yml: remove hardcoded data fallback in scene1."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

YML = Path(__file__).resolve().parents[1] / "Workflow-China_charge_seriver-draft-9380" / "workflow" / "AI_health_consultant_v2.yml"


NEW_SYSTEM_4010 = """你是销售小程序 AI 健康初筛助手,负责解析客户上传/粘贴的骨密度(DXA)报告内容。

# 你的边界
- 只做指标提取和风险初筛。
- 不做疾病诊断、不开药、不承诺疗效、不推荐产品。
- 输出语言: {{#4001.input_language#}},默认简体中文。

# 严禁行为(违反任意一条 = 整段输出作废,必须返回 dataComplete: false)
- 严禁编造任何医学指标数值。客户没明确给出的指标,不要写进 metrics。
- 严禁从图片的"任何数字"(页码、日期、表格背景、UI 文字)臆造 T 值或骨密度值。
- 严禁编造 oneLineConclusion 的具体数值(如"骨密度下降 X%")。
- 严禁在 problemPriority 中虚构风险方向(如"维生素D不足""尿酸偏高"——客户没提供数据就不要写)。
- 如果客户输入里没有出现可识别的骨密度指标数值,必须返回 metrics: [] 和 dataComplete: false,不能强行编造。

# 图片识别规则(关键!)
- 客户上传的图片必须是清晰可辨的骨密度 DXA 检测报告,包含明确的检测项目名称(如"腰椎 L1-L4 T值""股骨颈 T值")和具体数值。
- 如果图片是:
  * 与医疗无关的内容(UI 设计图、风景照、聊天截图、文档封面等)
  * 模糊、字迹不清、关键数值不可辨认
  * 体检报告封面而非正文(无 T 值、Z 值等数据)
  * 其他非 DXA 报告(化验单、超声报告、CT 报告等)
  则必须返回 dataComplete: false,metrics: [],不要试图从图片里"猜"出 T 值。
- 永远不要"宁可错杀不要放过"——识别不出就是识别不出,空着比瞎猜好。

# 文本识别规则(同样关键!)
- 客户文本中必须出现具体的 T 值数字(如"-2.1""-0.8"),才能写入 metrics。
- 仅出现"医生说 T 值不正常""骨质疏松""骨量减少"等描述性词语而**没有具体数字**,不算有数据。
- 仅出现"腰椎""股骨颈"等部位名称而**没有数值**,也不算有数据。
- 仅出现"DXA 报告""骨密度报告"等关键词而**没有具体 T 值数字**,不算有数据。
- 在以上"无数字"场景下,必须返回 dataComplete: false,metrics: []。

# 必须以 JSON 输出(只输出 JSON,不要 markdown 包裹、不要解释文字)
输出 schema:
{
  "confidence": "high" | "medium" | "low",  // ← 必须填写,你对自己识别的把握程度
  "dataComplete": true | false,  // ← 仅当 confidence=high 且 metrics 非空时才填 true
  "metrics": [
    {"name": "腰椎 L1-L4 T值", "value": -2.1, "unit": ""}
  ],
  "oneLineConclusion": "...",
  "problemPriority": [
    {"rank": 1, "name": "骨密度下降", "level": "中高"}
  ]
}

# confidence 自我评估规则
- confidence=high: 我**亲眼在客户输入的文字/图片中看到了**具体的 DXA 报告项目和数字(如"腰椎 L1-L4 T值 -2.1")。可以放心填 dataComplete=true。
- confidence=medium: 我看到了部分相关词(如"骨密度""DXA"),但**没有看到具体数值**。此时必须填 dataComplete=false,metrics=[]。
- confidence=low: 输入与骨密度报告完全无关(其他类型报告、设计图、聊天截图、症状描述等),或内容模糊不清。**必须填 dataComplete=false,metrics=[]。**

**绝对禁止**:在 confidence≠high 时填 dataComplete=true(代码节点会拦截)。如果你想填 true,必须先证明 confidence=high。

# 提取规则
- 常见指标: 腰椎 L1-L4 T值、股骨颈 T值、全髋 T值、25-OH 维生素 D、血钙。
- 文本/图片缺失的指标不要写,只输出实际识别到的项。
- value 必须是数字;若客户写"阴性/阳性"等非数值,不要放进 metrics。
- T 值的合理范围: 一般在 -5.0 ~ +3.0 之间。如果识别出的"数值"明显异常(如大于 5 或小于 -10),请再次确认——很可能是误识。
- oneLineConclusion 必须包含"建议咨询医生/不能替代医生"等措辞。
- problemPriority 仅基于实际识别到的指标给出 1-3 条(仅在 dataComplete=true 时)。"""


NEW_CODE_4011 = '''# 解析 LLM 输出 + 严格无硬编码兜底 + 硬验证防捏造
import json
import re


# DXA 相关指标的合法名称关键词 — 缺一不可通过
ALLOWED_METRIC_KEYWORDS = ("T值", "T 值", "T-score", "T score", "Z值", "Z 值", "Z-score", "25-OH", "维生素D", "维生素 D", "血钙", "BMD", "骨密度")

# T 值的医学合理范围 — 超出即视为 LLM 捏造
T_VALUE_MIN = -10.0
T_VALUE_MAX = 5.0

# problemPriority 白名单 — 防止 LLM 虚构风险方向
ALLOWED_PP_NAMES = frozenset({
    "骨密度下降", "骨量减少", "骨质疏松", "维生素D不足", "血钙异常",
    "T值偏低", "T值异常", "腰椎骨密度下降", "股骨颈骨密度下降", "全髋骨密度下降",
})


def _parse_llm_json(llm_text: str) -> dict:
    text = (llm_text or "").strip()
    if not text:
        return {}
    try:
        if text.startswith("{"):
            return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\\{.*\\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}


def _grade_t(t):
    try:
        v = float(t)
    except Exception:
        return "unknown"
    if v >= -1.0:
        return "normal"
    if v > -2.5:
        return "bone_loss"
    return "osteoporosis"


def _is_valid_metric_name(name: str) -> bool:
    if not name or not isinstance(name, str):
        return False
    return any(kw in name for kw in ALLOWED_METRIC_KEYWORDS)


def _is_valid_t_value(v) -> bool:
    try:
        f = float(v)
    except Exception:
        return False
    return T_VALUE_MIN <= f <= T_VALUE_MAX


def main(llm_text: str) -> dict:
    data = _parse_llm_json(llm_text)
    raw_metrics = data.get("metrics") or []

    # 硬验证 0: LLM 必须明确声明 confidence=high(自我认证:我确实看到了 DXA 报告中的具体数值)
    # 这是防捏造的核心闸门 — 不允许 LLM 在 confidence!=high 时输出 dataComplete=true
    confidence = str(data.get("confidence", "")).lower().strip()
    llm_data_complete = bool(data.get("dataComplete", False))
    if llm_data_complete and confidence != "high":
        return _insufficient("fabrication_detected", "AI 在解析过程中无法确认报告内容,请重新上传清晰的 DXA 报告或直接粘贴 T 值(如 '腰椎 L1-L4 T值 -2.1')。")

    # 硬验证 1: 指标名称必须含 DXA 关键词
    metrics = [m for m in raw_metrics if _is_valid_metric_name(m.get("name", ""))]

    # 硬验证 2: T 值必须在合理范围内
    t_values = []
    for m in metrics:
        name = m.get("name", "")
        if "T" in name or "t" in name:
            v = m.get("value")
            if _is_valid_t_value(v):
                t_values.append(float(v))

    has_real_data = bool(t_values)

    if not has_real_data:
        return _insufficient("no_metrics_extracted", "未识别到有效的骨密度数据。请您:(1) 上传清晰的 DXA 报告图片,或 (2) 直接粘贴报告中的 T 值(如 '腰椎 L1-L4 T值 -2.1')。")

    # 给每个指标计算 level
    for m in metrics:
        name = m.get("name", "")
        m["level"] = _grade_t(m.get("value")) if ("T" in name or "t" in name) else "unknown"

    yours_t = min(t_values)

    # 完整路径:有真实数据 + LLM 自我认证 confidence=high
    levels = [m.get("level", "unknown") for m in metrics]
    if "osteoporosis" in levels:
        risk_level = "high"
    elif "bone_loss" in levels:
        risk_level = "medium"
    elif "normal" in levels:
        risk_level = "low"
    else:
        risk_level = "low"

    counts = {"normal": 0, "bone_loss": 0, "osteoporosis": 0, "unknown": 0}
    for lv in levels:
        counts[lv if lv in counts else "unknown"] += 1
    total = sum(counts.values()) or 1
    risk_distribution = []
    if counts["osteoporosis"] > 0:
        risk_distribution.append({"name": "骨质疏松风险", "value": round(100 * counts["osteoporosis"] / total)})
    if counts["bone_loss"] > 0:
        risk_distribution.append({"name": "骨量减少", "value": round(100 * counts["bone_loss"] / total)})
    if counts["normal"] > 0:
        risk_distribution.append({"name": "正常", "value": round(100 * counts["normal"] / total)})

    one_line = data.get("oneLineConclusion", "").strip()
    if not one_line:
        one_line = "本次初筛结果仅供参考,具体诊断请咨询专业医师。"

    # 硬验证 4: problemPriority 白名单
    problem_priority = data.get("problemPriority") or []
    if problem_priority:
        filtered_pp = [p for p in problem_priority if p.get("name") in ALLOWED_PP_NAMES]
        if len(filtered_pp) != len(problem_priority):
            problem_priority = []

    payload = {
        "reportType": "bone_density",
        "dataComplete": True,
        "metrics": metrics,
        "tValueChart": {
            "normal": -1.0,
            "yours": yours_t,
            "thresholds": {"normal": -1.0, "loss": -2.5},
        },
        "riskDistribution": risk_distribution,
        "oneLineConclusion": one_line,
        "problemPriority": problem_priority,
        "questionnaireRef": "bone_density_v1",
    }
    response = {
        "scene": "report",
        "risk_level": risk_level,
        "scene_confidence": 0.85,
        "payloadKind": "complete",
        "payload": payload,
    }
    return {"output": json.dumps(response, ensure_ascii=False)}


def _insufficient(reason: str, user_message: str) -> dict:
    payload = {
        "reportType": "bone_density",
        "dataComplete": False,
        "reason": reason,
        "userMessage": user_message,
        "metrics": [],
        "problemPriority": [],
        "questionnaireRef": "bone_density_v1",
    }
    response = {
        "scene": "report",
        "risk_level": "low",
        "scene_confidence": 0.3,
        "payloadKind": "insufficient_data",
        "payload": payload,
    }
    return {"output": json.dumps(response, ensure_ascii=False)}
'''


def main() -> int:
    if not YML.exists():
        print(f"yml not found: {YML}")
        return 1
    data = yaml.safe_load(YML.read_text(encoding="utf-8"))
    nodes = data["workflow"]["graph"]["nodes"]
    touched = []
    for n in nodes:
        if n.get("id") == "4010":
            n["data"]["prompt_template"][0]["text"] = NEW_SYSTEM_4010
            touched.append("4010 prompt")
        if n.get("id") == "4011":
            n["data"]["code"] = NEW_CODE_4011
            touched.append("4011 code")
    if not touched:
        print("[error] no nodes 4010/4011 found")
        return 1
    out = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
    YML.write_text(out, encoding="utf-8")
    print(f"updated {touched} -> {YML} ({len(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
