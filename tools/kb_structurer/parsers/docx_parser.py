"""Word SOP → process MD 解析器(场景识别)。

输入:Word SOP 文档,按 H1/H2 标题识别场景,过滤包含指定关键词的章节。
"""
from __future__ import annotations
import re
from pathlib import Path


def _safe_filename(name: str) -> str:
    s = re.sub(r"[/\s\\\"'\*]+", "_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:40] if s else "process"


def _read_docx_text(path: str) -> list[tuple[str, str]]:
    """读取 Word 文档段落,返回 [(style, text), ...]。

    style: 'h1' / 'h2' / 'h3' / 'p'
    """
    try:
        import docx
    except ImportError:
        raise ImportError("需要 python-docx: pip install python-docx")

    d = docx.Document(path)
    out = []
    for para in d.paragraphs:
        style_name = (para.style.name or "").lower() if para.style else ""
        if "heading 1" in style_name or style_name == "title":
            style = "h1"
        elif "heading 2" in style_name:
            style = "h2"
        elif "heading 3" in style_name:
            style = "h3"
        else:
            style = "p"
        text = para.text.strip()
        if text:
            out.append((style, text))
    return out


def docx_to_process(input_path: str, output_dir: str,
                    sections: list[str],
                    prefix: str = "proc",
                    content_keywords: list[str] | None = None) -> int:
    """Word SOP → process MD(场景识别)。

    Args:
        input_path: Word 路径
        output_dir: 输出目录
        sections: 场景标题列表(顺序匹配)
        prefix: 文件名前缀
        content_keywords: 内容过滤关键词(只保留包含这些词的内容)

    Returns: 生成的 MD 数。
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if content_keywords is None:
        content_keywords = ["流程", "步骤", "操作", "入口", "常见", "拦截", "卡点"]

    paragraphs = _read_docx_text(input_path)

    sections_content: dict[str, list[tuple[str, str]]] = {}
    current_section = None
    current_paragraphs = []

    for style, text in paragraphs:
        if style in ("h1", "h2"):
            matched = None
            for sec in sections:
                if sec in text:
                    matched = sec
                    break
            if matched:
                if current_section:
                    sections_content[current_section] = current_paragraphs
                current_section = matched
                current_paragraphs = []
            else:
                if current_section:
                    current_paragraphs.append((style, text))
        else:
            if current_section:
                current_paragraphs.append((style, text))

    if current_section:
        sections_content[current_section] = current_paragraphs

    count = 0
    for idx, sec in enumerate(sections, 1):
        paras = sections_content.get(sec, [])
        lines = [f"# {sec}", ""]

        if paras:
            lines.append("## 步骤")
            lines.append("")
            step_n = 0
            for style, text in paras:
                if style == "h3":
                    step_n += 1
                    lines.append(f"### {step_n}. {text}")
                    lines.append("")
                elif style == "p":
                    if step_n == 0:
                        lines.append(text)
                    else:
                        lines.append(text)
                    lines.append("")
        else:
            lines.append("## 步骤")
            lines.append("")
            lines.append("*(待补充)*")
            lines.append("")

        kws = [sec]
        for kw in content_keywords:
            if any(kw in (t or "") for _, t in paras):
                kws.append(kw)
        lines.append("## 检索关键词")
        lines.append("")
        lines.append(", ".join(kws))
        lines.append("")

        fn = f"{prefix}_{idx:02d}_{_safe_filename(sec)}.md"
        (out_dir / fn).write_text("\n".join(lines), encoding="utf-8")
        count += 1

    return count