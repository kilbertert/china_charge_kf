"""CSV → menu MD 解析器(确定性拆分)。

按 (name, hierarchy_path) 分组,合并同菜单多 i18n 行。
输出文件名: {prefix}_{NNNN}_{菜单名}.md
"""
from __future__ import annotations
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional


def _safe_filename(name: str, max_len: int = 30) -> str:
    """生成安全的文件名 slug(保留中文,去特殊字符)。"""
    s = re.sub(r"[/\s\\\"'\*]+", "_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:max_len] if s else "unnamed"


def _gen_keywords(name: str, layer: str, top: str) -> list[str]:
    """从菜单名/路径/顶级菜单提取关键词。"""
    kws = {name}
    if top:
        kws.add(top)
    if layer:
        for part in layer.replace(">", " ").split():
            if len(part) >= 2:
                kws.add(part)
    # 2-gram 中文
    for c in re.findall(r"[一-龥]+", name):
        for i in range(len(c) - 1):
            kws.add(c[i:i + 2])
    return list(kws)[:20]


def _render_md(name: str, layer: str, top: str, items: list[dict], field_key_col: str, cn_col: str, en_col: str, component: str, menu_id: str) -> str:
    lines = ["# " + name, ""]
    lines.append("## 路径")
    lines.append("")
    if layer:
        lines.append("- **菜单层级**: " + layer)
    if top:
        lines.append("- **顶级菜单**: " + top)
    if menu_id:
        lines.append("- **菜单 ID**: `" + menu_id + "`")
    if component and component != "Layout":
        lines.append("- **前端组件**: `" + component + "`")
    lines.append("")

    if len(items) > 1:
        lines.append("## 字段中英文对照")
        lines.append("")
        lines.append("| 字段 Key | 中文 | English |")
        lines.append("|---|---|---|")
        for it in items[:50]:
            k = (it.get(field_key_col, "") or "").strip()
            cn = (it.get(cn_col, "") or "").strip()
            en = (it.get(en_col, "") or "").strip()
            if k and k != "(No I18n Found)":
                lines.append("| `" + k + "` | " + (cn or "-") + " | " + (en or "-") + " |")
        if len(items) > 50:
            lines.append("")
            lines.append("*(共 " + str(len(items)) + " 个字段,显示前 50)*")
        lines.append("")

    lines.append("## 检索关键词")
    lines.append("")
    kws = _gen_keywords(name, layer, top)
    lines.append(", ".join(kws))
    lines.append("")
    return "\n".join(lines)


def csv_to_menu(input_path: str, output_dir: str, encoding: str = "utf-8-sig",
                name_col: str = "name(菜单)", layer_col: str = "层级路径",
                id_col: str = "id(菜单id)", component_col: str = "component",
                field_key_col: str = "字段key", cn_col: str = "CN(中文对照)", en_col: str = "EN(英文对照)",
                top_col: str = "顶级菜单名称", max_rows_per_md: int = 200,
                prefix: str = "menu") -> int:
    """主函数:CSV → 菜单 MD。

    Returns: 生成的 MD 数。
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(input_path, encoding=encoding) as f:
        rows = list(csv.DictReader(f))

    # 按 (name, layer) 分组
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        name = (r.get(name_col) or "").strip()
        if not name:
            continue
        layer = (r.get(layer_col) or "").strip()
        groups[(name, layer)].append(r)

    # 按 name 排序(稳定输出)
    sorted_keys = sorted(groups.keys(), key=lambda k: (k[0], k[1]))

    count = 0
    for idx, (name, layer) in enumerate(sorted_keys, 1):
        items = groups[(name, layer)]
        first = items[0]
        menu_id = (first.get(id_col) or "").strip()
        component = (first.get(component_col) or "").strip()
        top = (first.get(top_col) or "").strip()

        # 拆过大 MD(如果 >max_rows,分页)
        chunks = [items[i:i + max_rows_per_md] for i in range(0, len(items), max_rows_per_md)]
        for ci, chunk in enumerate(chunks):
            md = _render_md(name, layer, top, chunk, field_key_col, cn_col, en_col, component, menu_id if ci == 0 else "")
            suffix = "" if len(chunks) == 1 else f"_part{ci + 1}"
            fn = f"{prefix}_{idx:04d}_{_safe_filename(name)}{suffix}.md"
            (out_dir / fn).write_text(md, encoding="utf-8")
            count += 1

    return count