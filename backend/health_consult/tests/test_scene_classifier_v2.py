"""Unit test for scene_classifier_v2 logic (extracted from yml).

Simulates the LLM's text output for each scenario, then validates the
code node's behavior:
  - LLM high confidence -> use LLM result
  - LLM low confidence / missing -> code safety net kicks in
  - Edge cases (no text + no image, has image only, negation, etc.)
"""

import json
import sys
from pathlib import Path

# Load code from yml
YML_PATH = Path(__file__).resolve().parents[3] / "Workflow-China_charge_seriver-draft-9380" / "workflow" / "AI_health_consultant_v2.yml"


def extract_code_from_yml() -> str:
    import yaml
    with open(YML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for node in data["workflow"]["graph"]["nodes"]:
        if node.get("id") == "4002" and node.get("data", {}).get("type") == "code":
            return node["data"]["code"]
    raise RuntimeError("node 4002 code not found")


def extract_llm_prompt_from_yml() -> str:
    import yaml
    with open(YML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for node in data["workflow"]["graph"]["nodes"]:
        if node.get("id") == "4080" and node.get("data", {}).get("type") == "llm":
            for msg in node["data"]["prompt_template"]:
                if msg.get("role") == "system":
                    return msg["text"]
    raise RuntimeError("node 4080 system prompt not found")


def execute_code(code_str: str, llm_text: str, text: str, has_image: bool, answers: str) -> dict:
    namespace = {"__builtins__": __builtins__}
    try:
        exec(code_str, namespace)
        main_fn = namespace["main"]
        return main_fn(llm_text=llm_text, text=text, has_image=has_image, answers=answers)
    except Exception as e:
        return {"_error": str(e)}


MOCK_LLM_RESPONSES = {
    "bone_density_text": (
        '56岁女性,已绝经,腰椎L1-L4 T值-2.1,股骨颈-1.8,全髋-1.5',
        {"scene": "report", "confidence": 0.95, "reasoning": "明确提及骨密度T值"}
    ),
    "leg_pain_symptom": (
        '我右小腿胀痛 腰间盘突出 压迫神经',
        {"scene": "symptom", "confidence": 0.92, "reasoning": "描述身体不适"}
    ),
    "leg_pain_serious": (
        '我左侧小腿突然肿胀发热,按压疼,伴胸闷气短',
        {"scene": "symptom", "confidence": 0.95, "reasoning": "危险信号"}
    ),
    "image_only": (
        '',
        {"scene": "report", "confidence": 0.7, "reasoning": "用户上传图片"}
    ),
    "greeting": (
        '你好',
        {"scene": "symptom", "confidence": 0.3, "reasoning": "问候语"}
    ),
    "negation": (
        '我腿不疼,没有不舒服',
        {"scene": "symptom", "confidence": 0.4, "reasoning": "否定句,提到症状词"}
    ),
    "product_question": (
        '补钙产品哪个好',
        {"scene": "product", "confidence": 0.88, "reasoning": "咨询产品"}
    ),
    "knee_pain_colloquial": (
        '我膝盖疼是怎么回事',
        {"scene": "symptom", "confidence": 0.9, "reasoning": "描述症状+问原因"}
    ),
    "report_interpretation": (
        '我体检报告上写T值-2.5是什么意思',
        {"scene": "report", "confidence": 0.85, "reasoning": "报告解读"}
    ),
    "treatment_product": (
        '治疗腿疼吃什么产品好',
        {"scene": "product", "confidence": 0.78, "reasoning": "咨询产品"}
    ),
}


def run_tests() -> int:
    code_str = extract_code_from_yml()
    sys_prompt = extract_llm_prompt_from_yml()

    print("=" * 70)
    print("scene_classifier_v2 test suite")
    print("=" * 70)
    print(f"\n[LLM system prompt] ({len(sys_prompt)} chars):")
    print(sys_prompt[:200] + ("..." if len(sys_prompt) > 200 else ""))
    print()

    test_cases = [
        # (case_id, expected_scene, expected_confidence_min, has_image, answers, description)
        ("bone_density_text",       "report",  0.7,  False, "",   "骨密度报告文本"),
        ("leg_pain_symptom",        "symptom", 0.7,  False, "",   "腿疼症状描述"),
        ("leg_pain_serious",        "symptom", 0.7,  False, "",   "危险信号描述"),
        ("image_only",              "report",  0.5,  True,  "",   "仅上传图片"),
        ("greeting",                "symptom", 0.0,  False, "",   "问候语(应低置信度)"),
        ("negation",                "symptom", 0.0,  False, "",   "否定(我腿不疼)"),
        ("product_question",        "product", 0.7,  False, "",   "产品咨询"),
        ("knee_pain_colloquial",    "symptom", 0.7,  False, "",   "口语化膝盖疼"),
        ("report_interpretation",   "report",  0.7,  False, "",   "报告解读"),
        ("treatment_product",       "product", 0.6,  False, "",   "产品(治疗用词)"),
    ]

    passed = 0
    failed = 0
    for case_id, exp_scene, exp_conf_min, has_image, answers, desc in test_cases:
        text_input, mock_llm = MOCK_LLM_RESPONSES[case_id]
        llm_text = json.dumps(mock_llm, ensure_ascii=False) if mock_llm else ""

        result = execute_code(code_str, llm_text, text_input, has_image, answers)
        actual_scene = result.get("scene", "_error")
        actual_conf = result.get("scene_confidence", 0.0)

        ok_scene = actual_scene == exp_scene
        ok_conf = actual_conf >= exp_conf_min
        status = "PASS" if (ok_scene and ok_conf) else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"[{status}] {case_id:25s} -> {actual_scene:8s}({actual_conf:.2f}) | expected: {exp_scene}(>={exp_conf_min:.1f}) | {desc}")
        if status == "FAIL":
            print(f"       result: {result}")

    print("\n--- Edge cases ---")
    edge_cases = [
        ("answers_bone",     '{"menopause":"yes"}',     "",    False, "report",  "骨量答案 menopause=yes"),
        ("answers_urgent",   '{"sudden_severe":"yes"}', "",    False, "symptom", "危险答案 sudden_severe=yes"),
        ("answers_leg",      '{"location":"knee"}',     "",    False, "symptom", "腿疼答案 location=knee"),
        ("llm_fail_keyword", "",                        "我腿疼",   False, "symptom",  "LLM失败时关键词兜底"),
        ("empty_everything", "",                        "",    False, "symptom",  "全空时低置信度兜底"),
    ]
    for case_id, ans, text_input, has_image, exp_scene, desc in edge_cases:
        result = execute_code(code_str, "", text_input, has_image, ans)
        actual_scene = result.get("scene", "_error")
        status = "PASS" if actual_scene == exp_scene else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        print(f"[{status}] {case_id:25s} -> {actual_scene:8s}({result.get('scene_confidence', 0):.2f}) | expected: {exp_scene} | {desc}")

    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed (total {passed + failed})")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
