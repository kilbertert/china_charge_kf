"""Generate kb-assets/KB-CHARGE-PILE.md from the (post-upload) MANIFEST.md.

Output layout: one H1 title, three H2 top-level sections (PC 后台 / 用户端 /
管家端), and one H3 per sub-section. Within each sub-section each image is
its own bullet whose first line is the English description (so Dify text
retrieval picks it up) and whose second line is the markdown image with the
same description as alt text and the OSS URL as ``src``.

Rows whose Notes column contains ``sample-only-no-publish`` are skipped.

Run from the project root:
    python scripts/build_kb_doc.py
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from collections import OrderedDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("build_kb_doc")

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "kb-assets" / "MANIFEST.md"
OUT_PATH = PROJECT_ROOT / "kb-assets" / "KB-CHARGE-PILE.md"

# --- Top-level sections ----------------------------------------------------

TOP_SECTIONS: list[dict] = [
    {
        "key": "PC",
        "title_zh": "PC 管理后端",
        "title_en": "Operator Console",
        "detect": lambda ctx: ctx.startswith("The operation of the PC management backend"),
    },
    {
        "key": "USER",
        "title_zh": "用户端",
        "title_en": "End-User App",
        "detect": lambda ctx: ctx.startswith("The user side operation"),
    },
    {
        "key": "BUTLER",
        "title_zh": "管家端",
        "title_en": "Partner Butler App",
        "detect": lambda ctx: ctx.startswith("The operation of the butler end"),
    },
]

# --- Sub-section translations (Chinese) ------------------------------------

SUB_SECTIONS: dict[tuple[str, str], str] = {
    # PC backend
    ("PC", "Role Management"): "角色管理",
    ("PC", "Shop Level"): "分润层级",
    ("PC", "Individual operator"): "个人运营商",
    ("PC", "Operator review for entry"): "运营商入驻审核",
    ("PC", "Add sites under the operator"): "运营商下添加场地",
    ("PC", "Site audit"): "场地审核",
    ("PC", "Billing Template (Charging Station)"): "计费模板（充电站）",
    ("PC", "Add product model"): "添加产品型号",
    ("PC", "equipment"): "设备管理",
    ("PC", "Placement equipment"): "设备投放",
    ("PC", "Charging coupons"): "充电优惠券",
    ("PC", "Equipment Failure List"): "设备故障列表",
    ("PC", "User Management"): "用户管理",
    ("PC", "Financial Management"): "财务管理",
    ("PC", "Order Management"): "订单管理",
    ("PC", "Operations Management"): "运营管理",
    ("PC", "Data View"): "数据看板",
    # User side
    ("USER", "Sign up"): "注册与登录",
    ("USER", "top-up"): "账户充值",
    ("USER", "place an order"): "扫码下单",
    ("USER", "Four wheel charging order"): "四轮充电订单",
    ("USER", "Placeholder fee order"): "占位费订单",
    ("USER", "venue"): "我的车辆",
    ("USER", "license plate"): "车牌管理",
    ("USER", "Change password"): "修改密码",
    ("USER", "Fault Repair"): "故障报修",
    # Butler end
    ("BUTLER", "Sign up"): "管家端注册",
    ("BUTLER", "Real name authentication (incoming)"): "实名认证",
    ("BUTLER", "Create venue"): "创建场地",
    ("BUTLER", "my venue"): "我的场地",
    ("BUTLER", "Create template"): "创建计费模板",
    ("BUTLER", "Venue association template"): "场地关联模板",
    ("BUTLER", "Placement equipment"): "设备投放",
    ("BUTLER", "data sector"): "数据板块",
    ("BUTLER", "order"): "订单管理",
    ("BUTLER", "Venue details"): "场地详情",
    ("BUTLER", "Profit withdrawal"): "利润提现",
}

# --- Helpers ---------------------------------------------------------------

def _parse_row(line: str) -> dict | None:
    """Parse one MANIFEST table row. Returns None for header/separator rows."""
    s = line.strip()
    if not s.startswith("|"):
        return None
    cells = [c.strip() for c in s.strip("|").split("|")]
    if len(cells) not in (6, 7) or not cells[0].isdigit():
        return None
    if len(cells) == 6:
        num, filename, context, desc, oss_key, notes = cells
        oss_url = ""
    else:
        num, filename, context, desc, oss_key, oss_url, notes = cells
    return {
        "num": int(num),
        "filename": filename.strip("`").strip(),
        "context": context,
        "description": desc,
        "oss_key": oss_key,
        "oss_url": oss_url,
        "notes": notes,
    }


def parse_manifest(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        r = _parse_row(line)
        if r is not None:
            rows.append(r)
    return rows


def classify(row: dict) -> tuple[str | None, str | None, str | None]:
    """Return (top_key, sub_name, example_name) for a row, or Nones if unclassified."""
    ctx = row["context"]
    for top in TOP_SECTIONS:
        if top["detect"](ctx):
            parts = [p.strip() for p in ctx.split(">")]
            sub = parts[1] if len(parts) > 1 else None
            example = parts[2] if len(parts) > 2 else None
            return top["key"], sub, example
    return None, None, None


def render_markdown(rows: list[dict]) -> str:
    """Render the KB document.

    Structure:
        # 充电桩产品知识库（图解手册）
            preamble
        ## 1. PC 管理后端（Operator Console）
            ### 1.1 角色管理
                - <description>
                  ![<alt>](<OSS URL>)
            ### 1.2 ...
        ## 2. 用户端（End-User App）
            ...
        ## 3. 管家端（Partner Butler App）
            ...
    """
    out: list[str] = []
    out.append("# 充电桩产品知识库（图解手册）\n")
    out.append(
        "> 本知识库供 H5 AI 客服在回答用户问题时检索图片素材。\n"
        "> 每张图片都按操作场景分组，图片 OSS URL 与图片说明在同一段，"
        "Dify 通过文本检索召回后会把图片 URL 一并转发给前端渲染。\n"
        "> 用户域名（生产）：`https://zcf.h5.qumall.qushiyun.com`；"
        "图片公网域名：`https://trendpower-ai-customer-service.oss-cn-guangzhou.aliyuncs.com`。\n"
    )

    buckets: "OrderedDict[tuple, list[dict]]" = OrderedDict()
    skipped: list[dict] = []

    for r in rows:
        if "sample-only-no-publish" in r["notes"].lower():
            skipped.append(r)
            continue
        if not r.get("oss_url"):
            skipped.append(r)
            continue
        top_key, sub, example = classify(r)
        if top_key is None or sub is None:
            skipped.append(r)
            continue
        key = (top_key, sub, example or "")
        buckets.setdefault(key, []).append(r)

    log.info(
        "rows=%d skipped=%d bucketed=%d groups=%d",
        len(rows),
        len(skipped),
        sum(len(v) for v in buckets.values()),
        len(buckets),
    )

    # Preserve the manifest (outline) order: walk top sections in declaration
    # order, then sub-sections in first-seen order, then examples.
    top_to_suborder: dict[str, list[str]] = {t["key"]: [] for t in TOP_SECTIONS}
    top_to_subexample: dict[tuple[str, str], list[str]] = {}
    for (top, sub, example), _ in buckets.items():
        if sub not in top_to_suborder[top]:
            top_to_suborder[top].append(sub)
        top_to_subexample.setdefault((top, sub), [])
        if example and example not in top_to_subexample[(top, sub)]:
            top_to_subexample[(top, sub)].append(example)

    top_counter = 0
    for top in TOP_SECTIONS:
        top_counter += 1
        out.append(
            f"\n## {top_counter}. {top['title_zh']}（{top['title_en']}）\n"
        )
        sub_counter = 0
        for sub in top_to_suborder[top["key"]]:
            sub_counter += 1
            sub_zh = SUB_SECTIONS.get((top["key"], sub), sub)
            out.append(f"\n### {top_counter}.{sub_counter} {sub_zh}\n")
            examples = top_to_subexample.get((top["key"], sub), [])
            # 1) First, the no-example group (rows that belong directly to the
            #    sub-section without an "Example - X" sub-leaf).
            no_example_key = (top["key"], sub, "")
            for r in sorted(buckets.get(no_example_key, []), key=lambda x: x["num"]):
                _render_bullet(out, r)
            # 2) Then each Example sub-leaf, if any.
            for ex_idx, example in enumerate(examples, start=1):
                out.append(f"\n#### {top_counter}.{sub_counter}.{ex_idx} {example}\n")
                key = (top["key"], sub, example)
                for r in sorted(buckets.get(key, []), key=lambda x: x["num"]):
                    _render_bullet(out, r)

    if skipped:
        out.append("\n---\n")
        out.append("\n## 附录：未发布图片\n")
        out.append(
            "\n以下图片因内容为后端测试二维码或被标记为 sample-only，"
            "未上传至 OSS，也未纳入知识库正文。\n"
        )
        for r in skipped:
            out.append(f"- row {r['num']}: `{r['filename']}` - {r['notes']}")

    return "\n".join(out) + "\n"


def _render_bullet(out: list[str], r: dict) -> None:
    """Append one bullet (description + image) to the output buffer."""
    desc = r["description"]
    url = r["oss_url"]
    out.append("")
    out.append(f"- {desc}")
    out.append(f"  ![{desc}]({url})")
    out.append("")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=OUT_PATH)
    args = parser.parse_args()

    text = MANIFEST_PATH.read_text(encoding="utf-8")
    rows = parse_manifest(text)
    log.info("Parsed %d manifest rows", len(rows))

    md = render_markdown(rows)
    args.out.write_text(md, encoding="utf-8")
    log.info("Wrote %s (%d lines)", args.out, md.count("\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
