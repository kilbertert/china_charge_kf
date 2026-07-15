#!/usr/bin/env python3
"""完整示例:把 data_processed.csv 解析为 menu_docs 并上传到 Dify。

用法:
    python3 examples/csv_to_menu.py
    # 或指定参数:
    python3 examples/csv_to_menu.py --input /path/data.csv --kb-id xxx
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.csv_parser import csv_to_menu
from uploader import bulk_upload


def main():
    p = argparse.ArgumentParser(description="CSV 菜单 → Dify KB 一键化")
    p.add_argument("--input", "-i", default="/path/to/data_processed.csv", help="CSV 输入路径")
    p.add_argument("--output", "-o", default="/tmp/menu_docs/", help="MD 输出目录")
    p.add_argument("--kb-id", default="", help="Dify KB ID(留空则只生成 MD 不上传)")
    p.add_argument("--api-base", default="http://127.0.0.1:8501")
    args = p.parse_args()

    print(f"=== Step 1: CSV → MD ===")
    count = csv_to_menu(args.input, args.output, encoding="utf-8-sig")
    print(f"✓ 生成 {count} 个 MD")

    if args.kb_id:
        print(f"\n=== Step 2: 上传到 Dify KB {args.kb_id[:8]} ===")
        result = bulk_upload(
            kb_id=args.kb_id,
            md_dir=args.output,
            api_base=args.api_base,
        )
        print(f"\n=== Done: uploaded={result['uploaded']}, errors={result['errors']} ===")
    else:
        print("\n未指定 --kb-id,跳过上传步骤")


if __name__ == "__main__":
    main()