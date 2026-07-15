"""Excel FAQ → faq MD 解析器(主题聚合)。

输入:FAQ Excel(节点/问题/答案),用主题映射 YAML 聚合到 N 个主题 MD。
"""
from __future__ import annotations
import re
from pathlib import Path
from collections import defaultdict
from typing import Any


def _load_yaml(path: str) -> dict[str, Any]:
    """最小 YAML loader(避免依赖 pyyaml,只支持简单 mapping/sequence)。"""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        out: dict[str, Any] = {}
        cur_key = None
        for line in open(path, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if line.startswith("  - ") or line.startswith("- "):
                continue  # 简单 parser 暂不支持 list-of-dict
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip(); v = v.strip()
                if v.startswith("[") and v.endswith("]"):
                    items = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                    out[k] = items
                else:
                    out[k] = v
        return out


def _safe_filename(name: str) -> str:
    s = re.sub(r"[/\s\\\"'\*]+", "_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:40] if s else "topic"


def xlsx_to_faq(input_path: str, output_dir: str, sheet: int | str = 0,
                topic_mapping_path: str = "", top_k_per_topic: int = 5,
                prefix: str = "faq") -> int:
    """Excel FAQ → 主题聚合 MD。

    Args:
        input_path: Excel 路径
        sheet: Sheet 索引或名
        topic_mapping_path: 主题映射 YAML,格式:
            topic_name:
              keywords: [节点A, 节点B, ...]
              description: 一行说明
        top_k_per_topic: 每主题保留的 Q&A 数(按出现顺序)

    Returns: 生成的 MD 数。
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError("需要 openpyxl: pip install openpyxl")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.load_workbook(input_path, data_only=True)
    ws = wb[sheet] if isinstance(sheet, str) else wb.worksheets[sheet]

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return 0
    headers = [str(h or "").strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        d = dict(zip(headers, [str(c).strip() if c is not None else "" for c in row]))
        data.append(d)

    mapping = _load_yaml(topic_mapping_path) if topic_mapping_path else {}

    # 按主题分组
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for d in data:
        node_field = next((k for k in d.keys() if "node" in k.lower() or "节点" in k), None)
        node_val = (d.get(node_field, "") if node_field else "").lower()

        matched_topic = None
        for topic, conf in mapping.items():
            kws = [k.lower() for k in (conf.get("keywords", []) if isinstance(conf, dict) else [])]
            if any(kw in node_val for kw in kws):
                matched_topic = topic
                break

        if matched_topic:
            by_topic[matched_topic].append(d)
        else:
            by_topic.setdefault("_unmapped", []).append(d)

    count = 0
    sorted_topics = sorted(by_topic.keys(), key=lambda t: (t == "_unmapped", t))

    for idx, topic in enumerate(sorted_topics, 1):
        items = by_topic[topic][:top_k_per_topic]
        if not items:
            continue

        q_field = next((k for k in items[0].keys() if "question" in k.lower() or "问题" in k), None)
        a_field = next((k for k in items[0].keys() if "answer" in k.lower() or "答案" in k), None)
        if not q_field or not a_field:
            print(f"WARN: topic {topic} 缺 question/answer 字段,跳过")
            continue

        q_en = next((k for k in items[0].keys() if "en" in k.lower() and "question" in k.lower()), None)
        a_en = next((k for k in items[0].keys() if "en" in k.lower() and "answer" in k.lower()), None)

        lines = [f"# {topic}", ""]
        topic_conf = mapping.get(topic, {})
        if isinstance(topic_conf, dict) and topic_conf.get("description"):
            lines.append(f"> {topic_conf['description']}")
            lines.append("")
        lines.append("## 常见问题")
        lines.append("")
        for i, item in enumerate(items, 1):
            q = item.get(q_field, "")
            a = item.get(a_field, "")
            if q_en and item.get(q_en):
                lines.append(f"### Q{i} ({item.get(q_en, '')})")
                lines.append("")
                lines.append(f"**中文:** {q}")
                lines.append("")
                lines.append(f"**答案:** {a}")
                if a_en and item.get(a_en):
                    lines.append("")
                    lines.append(f"**EN Answer:** {item.get(a_en, '')}")
            else:
                lines.append(f"### Q{i}")
                lines.append("")
                lines.append(f"**问:** {q}")
                lines.append("")
                lines.append(f"**答:** {a}")
            lines.append("")
        kws = [topic] + [k for k in (topic_conf.get("keywords", []) if isinstance(topic_conf, dict) else [])]
        lines.append("## 检索关键词")
        lines.append("")
        lines.append(", ".join(kws))
        lines.append("")

        fn = f"{prefix}_{idx:02d}_{_safe_filename(topic)}.md"
        (out_dir / fn).write_text("\n".join(lines), encoding="utf-8")
        count += 1

    return count