"""Working example: AI Health Consultant scene_classifier (LLM + code safety net).

This is the exact pipeline deployed in production:
  - LLM node 4080: classifies input into report / symptom / product
    with strict JSON output and explicit "report 强信号词" rules
  - Code node 4002: 6-layer safety net that handles low-confidence
    LLM output, image-only inputs, negation, greetings, and answers
    priority

Run as a script:
    python examples/health_consult_v2.py build      # emit yml
    python examples/health_consult_v2.py test-code  # offline unit test
    python examples/health_consult_v2.py deploy     # SSH to Dify + DB update
    python examples/health_consult_v2.py verify     # live HTTP test cases

Or import it and call `build_workflow()` / `build_test_cases()`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from dify_workflow_toolkit import (  # noqa: E402
    CodeNode,
    Deployer,
    EndNode,
    LLMNode,
    SSHClient,
    StartNode,
    TestCase,
    Variable,
    Verifier,
    Workflow,
)
from dify_workflow_toolkit.verifier import format_report, run_code_test  # noqa: E402


LLM_SYSTEM_PROMPT = """你是 AI 健康咨询的场景分类器。给定用户输入(text + image + answers),
将其归入以下三类之一:

  - "report":  涉及体检/检查报告、医学检查指标值、报告解读
  - "symptom": 涉及身体不适、症状描述(疼痛/酸胀/红肿等)
  - "product": 涉及产品咨询、营养品选择、怎么买/推荐

【关键规则】

【重要】report 强信号词(必须判定为 report,不要被"我56岁/我女性"等描述带偏):
- 出现具体医学指标数值: T值 / T 值 / DXA / 骨密度 / 骨量 / 25-OH / 维生素 D / 血钙 / 碱性磷酸酶 / 骨钙素
- 出现"体检报告/我的报告/检查报告/化验单/检验单"等报告类词

【边界 case】
- 仅上传图片(无文字) → report (用户大概率是来上传报告)
- 问候语("你好/在吗") → symptom (默认场景),confidence 给 0.3
- 否定句("我腿不疼/我没有不舒服") → symptom (用户提到身体部位),confidence 给 0.4
- 报告解读问题("T值-2.5 是什么意思") → report

【输出格式 — 严格 JSON,不要任何额外文字】
{
  "scene": "report" | "symptom" | "product",
  "confidence": 0.0-1.0,
  "reasoning": "一句话说明判定理由"
}
"""


LLM_USER_PROMPT = """用户输入:
- text: {{#4001.text#}}
- has_image: {{#4001.has_image#}}
- answers: {{#4001.answers#}}

请输出 JSON 判定。"""


CODE_SAFETY_NET = r'''
import json
import re

_REPORT_KEYWORDS = [
    "T值", "T 值", "DXA", "骨密度", "骨量", "骨量减少", "骨质疏松",
    "25-OH", "维生素 D", "血钙", "碱性磷酸酶", "骨钙素",
    "体检报告", "我的报告", "检查报告", "化验单", "检验单",
    "T-score", "T score", "骨扫描",
]
_SYMPTOM_KEYWORDS = [
    "疼", "痛", "酸", "胀", "麻", "木", "痒", "烧", "凉", "不适",
    "肿胀", "红肿", "发热", "抽筋", "僵硬", "活动受限",
    "胸闷", "气短", "头晕", "恶心", "呕吐",
]
_PRODUCT_KEYWORDS = [
    "补钙", "产品", "推荐", "哪个好", "怎么选", "营养品",
    "钙片", "氨糖", "软骨素", "维生素D", "蛋白粉",
]
_DANGER_KEYWORDS = [
    "突然肿胀", "肿胀发热", "按压疼", "胸闷气短",
    "夜间痛", "静息痛", "红肿热痛",
]

_ANSWERS_TAGS = {
    "menopause": "report",
    "tvalue_lumbar": "report",
    "sudden_severe": "symptom",
    "trauma": "symptom",
    "location": "symptom",
    "duration": "symptom",
    "trigger": "symptom",
    "intensity": "symptom",
    "age": "report",
    "gender": "report",
}


def _parse_llm(llm_text: str) -> dict:
    if not llm_text:
        return {}
    try:
        return json.loads(llm_text)
    except Exception:
        pass
    m = re.search(r"\{[^{}]*\}", llm_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    m = re.search(r"\{.*\}", llm_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)


def _answers_priority(answers: str):
    if not answers:
        return None
    try:
        a = json.loads(answers)
    except Exception:
        return None
    if not isinstance(a, dict):
        return None
    for key in a:
        if key in _ANSWERS_TAGS:
            return _ANSWERS_TAGS[key], 0.85
    return None


def main(llm_text: str = "", text: str = "", has_image: bool = False, answers: str = "") -> dict:
    text = (text or "").strip()
    has_image = bool(has_image)

    ans = _answers_priority(answers)
    if ans is not None:
        scene, conf = ans
        return {
            "scene": scene,
            "scene_confidence": conf,
            "reasoning": "based on questionnaire answers",
            "_source": "answers",
        }

    llm = _parse_llm(llm_text)
    llm_scene = llm.get("scene", "")
    llm_conf = float(llm.get("confidence", 0.0) or 0.0)

    if llm_scene in ("report", "symptom", "product") and llm_conf >= 0.5:
        return {
            "scene": llm_scene,
            "scene_confidence": llm_conf,
            "reasoning": llm.get("reasoning", "from LLM"),
            "_source": "llm",
        }

    if not text and has_image:
        return {
            "scene": "report",
            "scene_confidence": 0.7,
            "reasoning": "user uploaded an image (likely a report)",
            "_source": "code-image-only",
        }
    if not text and not has_image:
        return {
            "scene": "symptom",
            "scene_confidence": 0.2,
            "reasoning": "no input — default to symptom",
            "_source": "code-empty",
        }

    if llm_scene in ("report", "symptom", "product"):
        keyword_map = {
            "report": _REPORT_KEYWORDS,
            "symptom": _SYMPTOM_KEYWORDS,
            "product": _PRODUCT_KEYWORDS,
        }
        if _has_any(text, keyword_map[llm_scene]):
            return {
                "scene": llm_scene,
                "scene_confidence": max(llm_conf, 0.55),
                "reasoning": llm.get("reasoning", "from LLM hint + keyword confirm"),
                "_source": "llm+keyword",
            }

    scores = {
        "report": sum(1 for k in _REPORT_KEYWORDS if k in text),
        "symptom": sum(1 for k in _SYMPTOM_KEYWORDS if k in text),
        "product": sum(1 for k in _PRODUCT_KEYWORDS if k in text),
    }
    best_scene = max(scores, key=lambda k: scores[k])
    best_score = scores[best_scene]
    if best_score > 0:
        return {
            "scene": best_scene,
            "scene_confidence": min(0.45 + 0.1 * best_score, 0.85),
            "reasoning": f"keyword score: {scores}",
            "_source": "keyword",
        }

    if _has_any(text, _DANGER_KEYWORDS):
        return {
            "scene": "symptom",
            "scene_confidence": 0.9,
            "risk_level": "urgent",
            "reasoning": "danger signal keyword matched",
            "_source": "danger",
        }

    if llm_scene in ("report", "symptom", "product"):
        return {
            "scene": llm_scene,
            "scene_confidence": 0.3,
            "reasoning": "no keyword match; using LLM hint with low conf",
            "_source": "llm-low",
        }
    return {
        "scene": "symptom",
        "scene_confidence": 0.2,
        "reasoning": "no signal at all; defaulting to symptom",
        "_source": "default",
    }
'''


def build_workflow() -> Workflow:
    wf = Workflow(
        name="AI_health_consultant_v2",
        description="AI 健康咨询场景分类器 (LLM + code 6-layer safety net)",
    )

    wf.add(StartNode(
        id="4001",
        title="开始",
        variables=[
            Variable(variable="text", label="用户文本", type="paragraph", max_length=2000),
            Variable(variable="has_image", label="是否有图片", type="boolean", default=False),
            Variable(variable="answers", label="问卷答案 JSON", type="paragraph", default=""),
        ],
    ))

    wf.add(LLMNode(
        id="4080",
        title="scene_classifier_LLM",
        system_prompt=LLM_SYSTEM_PROMPT,
        user_prompt=LLM_USER_PROMPT,
        json_mode=True,
        temperature=0.2,
        max_tokens=512,
    ))

    wf.add(CodeNode(
        id="4002",
        title="scene_classifier_safety_net",
        code=CODE_SAFETY_NET,
        variables=[
            {"variable": "llm_text", "value_selector": ["4080", "text"]},
            {"variable": "text", "value_selector": ["4001", "text"]},
            {"variable": "has_image", "value_selector": ["4001", "has_image"]},
            {"variable": "answers", "value_selector": ["4001", "answers"]},
        ],
        outputs={
            "type": "object",
            "properties": [
                {"value": {"type": "string"}, "key": "scene"},
                {"value": {"type": "number"}, "key": "scene_confidence"},
                {"value": {"type": "string"}, "key": "reasoning"},
            ],
            "additionalProperties": True,
        },
    ))

    wf.add(EndNode(id="4099", title="结束", outputs=[
        {"variable": "output", "value_selector": ["4002", "scene"]},
        {"variable": "confidence", "value_selector": ["4002", "scene_confidence"]},
    ]))

    wf.connect("4001", "4080")
    wf.connect("4080", "4002")
    wf.connect("4002", "4099")

    return wf


MOCK_LLM = {
    "bone_density_text":     '{"scene": "report",  "confidence": 0.95, "reasoning": "明确骨密度T值"}',
    "leg_pain_symptom":      '{"scene": "symptom", "confidence": 0.92, "reasoning": "描述身体不适"}',
    "leg_pain_serious":      '{"scene": "symptom", "confidence": 0.95, "reasoning": "危险信号"}',
    "image_only":            '{"scene": "report",  "confidence": 0.7,  "reasoning": "用户上传图片"}',
    "greeting":              '{"scene": "symptom", "confidence": 0.3,  "reasoning": "问候语"}',
    "negation":              '{"scene": "symptom", "confidence": 0.4,  "reasoning": "否定句"}',
    "product_question":      '{"scene": "product", "confidence": 0.88, "reasoning": "咨询产品"}',
    "knee_pain_colloquial":  '{"scene": "symptom", "confidence": 0.9,  "reasoning": "症状+问原因"}',
    "report_interpretation": '{"scene": "report",  "confidence": 0.85, "reasoning": "报告解读"}',
    "treatment_product":     '{"scene": "product", "confidence": 0.78, "reasoning": "咨询产品"}',
}


def build_test_cases() -> list[TestCase]:
    return [
        TestCase(case_id="bone_density_text", text="我56岁,女性,已绝经,腰椎L1-L4 T值-2.1,骨量减少",
                 expected={"scene": "report", "scene_confidence": ">=0.7"}, description="骨密度报告文本"),
        TestCase(case_id="leg_pain_symptom", text="我右小腿胀痛 腰间盘突出 压迫神经",
                 expected={"scene": "symptom", "scene_confidence": ">=0.7"}, description="腿疼症状描述"),
        TestCase(case_id="leg_pain_serious", text="我左侧小腿突然肿胀发热,按压疼,伴胸闷气短",
                 expected={"scene": "symptom", "scene_confidence": ">=0.7"}, description="危险信号描述"),
        TestCase(case_id="image_only", text="", has_image=True,
                 expected={"scene": "report", "scene_confidence": ">=0.5"}, description="仅上传图片"),
        TestCase(case_id="greeting", text="你好",
                 expected={"scene": "symptom", "scene_confidence": ">=0.0"}, description="问候语 (应低置信度)"),
        TestCase(case_id="negation", text="我腿不疼,没有不舒服",
                 expected={"scene": "symptom", "scene_confidence": ">=0.0"}, description="否定 (我腿不疼)"),
        TestCase(case_id="product_question", text="补钙产品哪个好",
                 expected={"scene": "product", "scene_confidence": ">=0.7"}, description="产品咨询"),
        TestCase(case_id="knee_pain_colloquial", text="我膝盖疼是怎么回事",
                 expected={"scene": "symptom", "scene_confidence": ">=0.7"}, description="口语化膝盖疼"),
        TestCase(case_id="report_interpretation", text="我体检报告上写T值-2.5是什么意思",
                 expected={"scene": "report", "scene_confidence": ">=0.7"}, description="报告解读"),
        TestCase(case_id="treatment_product", text="治疗腿疼吃什么产品好",
                 expected={"scene": "product", "scene_confidence": ">=0.5"}, description="产品 (治疗用词)"),
    ]


def cmd_build() -> int:
    wf = build_workflow()
    out_path = _HERE / "health_consult_v2.yml"
    out_path.write_text(wf.to_yaml(), encoding="utf-8")
    print(f"wrote {out_path} ({len(wf.nodes())} nodes, {len(wf.edges())} edges)")
    return 0


def cmd_test_code() -> int:
    code = CODE_SAFETY_NET
    cases = build_test_cases()
    passed = failed = 0
    for c in cases:
        llm_text = MOCK_LLM.get(c.case_id, "")
        result = run_code_test(
            code,
            inputs={"text": c.text, "has_image": c.has_image, "answers": c.answers},
            llm_text=llm_text,
        )
        exp_conf_s = c.expected.get("scene_confidence", ">=0.0")
        threshold = float(exp_conf_s.lstrip(">=").lstrip("<=")) if isinstance(exp_conf_s, str) else exp_conf_s
        exp_scene = c.expected.get("scene", "")
        ok = result.get("scene") == exp_scene and result.get("scene_confidence", 0) >= threshold
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"[{status}] {c.case_id:25s} -> scene={result.get('scene')!r:10s} conf={result.get('scene_confidence', 0):.2f}  (expected {exp_scene!r} >= {threshold})")
    print(f"\n{passed}/{passed+failed} passed")
    return 0 if failed == 0 else 1


def cmd_deploy(ssh_host: str, ssh_user: str, ssh_password: str, app_id: str) -> int:
    yml_path = _HERE / "health_consult_v2.yml"
    if not yml_path.exists():
        cmd_build()
    with SSHClient(ssh_host, user=ssh_user, password=ssh_password) as ssh:
        deployer = Deployer(ssh)
        result = deployer.deploy(
            yml_path,
            app_id,
            restart=True,
            must_have_nodes=["4080", "4002", "4003", "4099"],
        )
    print(result)
    return 0 if result.verified else 1


def cmd_verify(ssh_host: str, ssh_user: str, ssh_password: str, endpoint: str) -> int:
    cases = build_test_cases()
    with SSHClient(ssh_host, user=ssh_user, password=ssh_password) as ssh:
        v = Verifier(ssh, default_endpoint=endpoint)
        report = v.run(cases)
    print(format_report(report))
    return 0 if report.failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="emit yml to disk").set_defaults(func=lambda a: cmd_build())
    sub.add_parser("test-code", help="run inline code test (no LLM)").set_defaults(func=lambda a: cmd_test_code())

    p_d = sub.add_parser("deploy", help="deploy to Dify over SSH")
    p_d.add_argument("--ssh-host", required=True)
    p_d.add_argument("--ssh-user", default="root")
    p_d.add_argument("--ssh-password", default=os.environ.get("DIFY_SSH_PASSWORD"))
    p_d.add_argument("--app-id", required=True)
    p_d.set_defaults(func=lambda a: cmd_deploy(a.ssh_host, a.ssh_user, a.ssh_password, a.app_id))

    p_v = sub.add_parser("verify", help="run live HTTP test cases")
    p_v.add_argument("--ssh-host", required=True)
    p_v.add_argument("--ssh-user", default="root")
    p_v.add_argument("--ssh-password", default=os.environ.get("DIFY_SSH_PASSWORD"))
    p_v.add_argument("--endpoint", default="http://127.0.0.1:8013/api/health-consult/chat")
    p_v.set_defaults(func=lambda a: cmd_verify(a.ssh_host, a.ssh_user, a.ssh_password, a.endpoint))

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
