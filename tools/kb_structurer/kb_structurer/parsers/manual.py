"""手工 YAML → MD(模板填充)。

用 Jinja2 模板 + YAML 数据生成 MD。
适合专家手工写的种子数据(快速迭代)。
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any


def _load_yaml(path: str) -> Any:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        raise ImportError("需要 pyyaml: pip install pyyaml")


def from_template(template_path: str, data_path: str, output_dir: str, batch: bool = False) -> int:
    """YAML + Jinja2 模板 → MD。

    Args:
        template_path: Jinja2 模板路径(.j2)
        data_path: 数据 YAML(单 dict 或 list[dict])
        output_dir: 输出目录
        batch: 当 True 时 data 是 list,逐项渲染(文件名取 slug 字段)

    Returns: 生成的 MD 数。
    """
    try:
        from jinja2 import Template
    except ImportError:
        raise ImportError("需要 jinja2: pip install jinja2")

    tpl_src = Path(template_path).read_text(encoding="utf-8")
    data = _load_yaml(data_path)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    items = data if (batch and isinstance(data, list)) else [data]
    tpl = Template(tpl_src)

    for i, item in enumerate(items, 1):
        rendered = tpl.render(**item)
        slug = item.get("slug") or item.get("name") or item.get("title") or "doc"
        slug = re.sub(r"[/\s\\\"'\*]+", "_", slug)[:40].strip("_") or "doc"
        prefix = item.get("prefix", "md")
        fn = f"{prefix}_{i:02d}_{slug}.md" if batch else f"{slug}.md"
        (out_dir / fn).write_text(rendered, encoding="utf-8")

    return len(items)