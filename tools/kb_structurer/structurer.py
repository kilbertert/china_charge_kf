#!/usr/bin/env python3
"""KB Structurer CLI — 充电桩客服知识库拆解工具入口。

子命令:
  csv-to-menu       CSV 菜单文件 → 菜单 MD(确定性拆分)
  xlsx-to-faq       Excel FAQ   → FAQ MD(主题聚合)
  docx-to-process   Word SOP    → 流程 MD(场景识别)
  from-template     手工 YAML   → MD(模板填充)
  upload-to-dify    MD 目录     → Dify KB(批量上传)

示例:
  python3 structurer.py csv-to-menu --input data.csv --output /tmp/menu_docs/
  python3 structurer.py upload-to-dify --kb-id c1b76f43 --md-dir /tmp/menu_docs/ --api-key app-xxx
"""
from __future__ import annotations
import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parsers.csv_parser import csv_to_menu
from parsers.xlsx_parser import xlsx_to_faq
from parsers.docx_parser import docx_to_process
from parsers.manual import from_template
from uploader import bulk_upload


def main():
    parser = argparse.ArgumentParser(
        prog="structurer",
        description="充电桩客服知识库拆解工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s csv-to-menu --input data.csv --output /tmp/menu_docs/
  %(prog)s xlsx-to-faq --input faq.xlsx --output /tmp/seed_faq/ --topic-mapping topic.yaml
  %(prog)s docx-to-process --input sop.docx --output /tmp/seed_proc/
  %(prog)s from-template --template t.md.j2 --data d.yaml --output /tmp/seed_biz/
  %(prog)s upload-to-dify --kb-id xxx --md-dir /tmp/menu_docs/ --api-key app-xxx
        """,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # csv-to-menu
    p_csv = sub.add_parser("csv-to-menu", help="CSV 菜单 → menu MD")
    p_csv.add_argument("--input", "-i", required=True, help="CSV 输入路径")
    p_csv.add_argument("--output", "-o", required=True, help="MD 输出目录")
    p_csv.add_argument("--encoding", default="utf-8-sig", help="CSV 编码 (default utf-8-sig for Excel-exported)")
    p_csv.add_argument("--max-rows-per-md", type=int, default=200, help="单 MD 最大行数")
    p_csv.add_argument("--name-column", default="name(菜单)", help="菜单名列名")
    p_csv.add_argument("--layer-column", default="层级路径", help="层级路径列名")
    p_csv.add_argument("--id-column", default="id(菜单id)", help="菜单 ID 列名")
    p_csv.add_argument("--prefix", default="menu", help="文件名前缀")

    # xlsx-to-faq
    p_xlsx = sub.add_parser("xlsx-to-faq", help="Excel FAQ → faq MD")
    p_xlsx.add_argument("--input", "-i", required=True, help="Excel 输入路径")
    p_xlsx.add_argument("--output", "-o", required=True, help="MD 输出目录")
    p_xlsx.add_argument("--sheet", default=0, help="Sheet 名/索引")
    p_xlsx.add_argument("--topic-mapping", required=True, help="主题映射 YAML 配置")
    p_xlsx.add_argument("--prefix", default="faq", help="文件名前缀")
    p_xlsx.add_argument("--top-k-per-topic", type=int, default=5, help="每主题保留 Q&A 数")

    # docx-to-process
    p_docx = sub.add_parser("docx-to-process", help="Word SOP → process MD")
    p_docx.add_argument("--input", "-i", required=True, help="Word 输入路径")
    p_docx.add_argument("--output", "-o", required=True, help="MD 输出目录")
    p_docx.add_argument("--sections", required=True, help="场景标题(逗号分隔)")
    p_docx.add_argument("--prefix", default="proc", help="文件名前缀")

    # from-template
    p_tmpl = sub.add_parser("from-template", help="YAML → MD (Jinja2 模板)")
    p_tmpl.add_argument("--template", "-t", required=True, help="Jinja2 模板路径")
    p_tmpl.add_argument("--data", "-d", required=True, help="数据 YAML 路径")
    p_tmpl.add_argument("--output", "-o", required=True, help="MD 输出目录")
    p_tmpl.add_argument("--batch", action="store_true", help="data 是 list 时批量生成")

    # upload-to-dify
    p_up = sub.add_parser("upload-to-dify", help="MD 目录 → Dify KB")
    p_up.add_argument("--kb-id", required=True, help="Dify KB ID (uuid)")
    p_up.add_argument("--md-dir", required=True, help="MD 文件目录")
    p_up.add_argument("--api-key", required=True, help="Dify API key")
    p_up.add_argument("--api-base", default="http://127.0.0.1:8501", help="Dify API base")
    p_up.add_argument("--sleep", type=float, default=0.15, help="每文件间隔(秒)")

    args = parser.parse_args()

    if args.cmd == "csv-to-menu":
        count = csv_to_menu(
            input_path=args.input,
            output_dir=args.output,
            encoding=args.encoding,
            name_col=args.name_column,
            layer_col=args.layer_column,
            id_col=args.id_column,
            max_rows_per_md=args.max_rows_per_md,
            prefix=args.prefix,
        )
        print(f"✓ 生成 {count} 个 menu MD → {args.output}")

    elif args.cmd == "xlsx-to-faq":
        count = xlsx_to_faq(
            input_path=args.input,
            output_dir=args.output,
            sheet=args.sheet,
            topic_mapping_path=args.topic_mapping,
            top_k_per_topic=args.top_k_per_topic,
            prefix=args.prefix,
        )
        print(f"✓ 生成 {count} 个 faq MD → {args.output}")

    elif args.cmd == "docx-to-process":
        count = docx_to_process(
            input_path=args.input,
            output_dir=args.output,
            sections=[s.strip() for s in args.sections.split(",")],
            prefix=args.prefix,
        )
        print(f"✓ 生成 {count} 个 process MD → {args.output}")

    elif args.cmd == "from-template":
        count = from_template(
            template_path=args.template,
            data_path=args.data,
            output_dir=args.output,
            batch=args.batch,
        )
        print(f"✓ 生成 {count} 个 MD → {args.output}")

    elif args.cmd == "upload-to-dify":
        result = bulk_upload(
            kb_id=args.kb_id,
            md_dir=args.md_dir,
            api_key=args.api_key,
            api_base=args.api_base,
            sleep=args.sleep,
        )
        print(f"\n=== 上传结果 ===")
        print(f"  上传: {result['uploaded']}")
        print(f"  失败: {result['errors']}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()